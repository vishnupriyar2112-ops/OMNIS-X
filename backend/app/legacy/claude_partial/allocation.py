"""Constraint solving primitives (Google OR-Tools CP-SAT with transparent rule-based fallbacks).

Every public function returns a dict that includes `solver`: the name of the engine that
produced the answer ("OR-Tools CP-SAT (OPTIMAL)", "Rule-based greedy fallback", ...), so the UI
never claims an optimisation that did not happen.
"""
from collections import Counter, defaultdict
from datetime import timedelta
from itertools import combinations

from ..engines.campus import overlap, START_HOURS, WORK_END
from ..engines.conflicts import room_fits

try:  # OR-Tools is optional at import time; the fallback keeps the app usable without it.
    from ortools.sat.python import cp_model
    HAVE_ORTOOLS = True
except Exception:  # pragma: no cover - depends on environment
    cp_model = None
    HAVE_ORTOOLS = False

FALLBACK = "Rule-based greedy fallback"
TIME_LIMIT_S = 8.0


def _label(solver, status):
    return f"OR-Tools CP-SAT ({solver.StatusName(status)})"


def _solve(model):
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = TIME_LIMIT_S
    status = solver.Solve(model)
    ok = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    return solver, status, ok


def _t_overlap(a, b):
    return a["date"] == b["date"] and overlap(a["start"], a["dur"], b["start"], b["dur"])


# --------------------------------------------------------------------------
# Relocation: same time slot, different room
# --------------------------------------------------------------------------
def room_candidates(campus, occ, t, allowed_rooms, ignore):
    cands, why, considered = [], Counter(), 0
    for r in campus.rooms.values():
        if r["id"] not in allowed_rooms or r["room_type"] not in t["types"]:
            continue
        considered += 1
        if not room_fits(campus, r, t["size"], None, t.get("lab_type")):
            why["capacity or lab type" if r["capacity"] < t["size"] or (t.get("lab_type") and r.get("lab_type") != t["lab_type"]) else "equipment"] += 1
            continue
        if any((r.get("equipment") or {}).get(k, 0) < v for k, v in t["need"].items()):
            why["equipment"] += 1
            continue
        if occ.room_busy(r["id"], t["date"], t["weekday"], t["start"], t["dur"], ignore=ignore):
            why["already booked at that time"] += 1
            continue
        cands.append(r)
    return cands, why, considered


def relocate(campus, occ, tasks, healthy_rooms):
    """Move each task to another healthy room in the SAME time slot."""
    ignore = {t["id"] for t in tasks}
    cands, reasons = {}, {}
    for t in tasks:
        c, why, n = room_candidates(campus, occ, t, healthy_rooms, ignore)
        cands[t["key"]] = c
        reasons[t["key"]] = (n, why)
    chosen, solver_name = None, FALLBACK
    if HAVE_ORTOOLS and tasks:
        try:
            m = cp_model.CpModel()
            x = {(t["key"], r["id"]): m.NewBoolVar(f"x_{t['key']}_{r['id']}") for t in tasks for r in cands[t["key"]]}
            for t in tasks:
                vs = [x[(t["key"], r["id"])] for r in cands[t["key"]]]
                if vs:
                    m.AddAtMostOne(vs)
            for a, b in combinations(tasks, 2):