"""Intelligent Recovery Engine.

For a finished simulation it builds *several* candidate recovery plans, checks each against the
real constraints (capacity, equipment, availability, workload, generator/bandwidth/seat limits),
ranks the feasible ones and keeps the infeasible ones with an explanation.

Plan score (documented in the UI): 100 x (0.60 coverage + 0.25 speed + 0.15 low-disruption)
 - coverage   share of displaced work/people the plan actually restores
 - speed      1 - estimated_hours/24 (floor 0)
 - disruption strategy-specific penalty (continue in place 0.10 ... postpone 0.70)
"""
import math
from datetime import timedelta

from ..engines.campus import DAYS, fmt_hour, parse_date, WORK_END
from ..engines.conflicts import equipment_need
from ..simulation.cascade import FAILED_STATES
from . import allocation as A

ROOM_KINDS = {"lab", "classroom", "exam_hall", "auditorium"}


# ---------------------------------------------------------------- tasks
def _slot(date, start, dur):
    d = parse_date(date)
    return f"{DAYS[d.weekday()]} {d.isoformat()} {fmt_hour(start)}-{fmt_hour(start + dur)}"


def make_tasks(campus, sim, failed_faculty=()):
    internal = sim["_internal"]
    windows = internal["windows"]
    tasks = []
    for s in internal["sess_w"]:
        w = next((w for w in windows if w["weekday"] == s["day"]), windows[0])
        room = campus.rooms[s["room_id"]]
        is_lab = s["kind"] == "lab"
        tasks.append({"key": f"{s['id']}@{w['date']}", "id": s["id"], "type": "session", "kind": s["kind"], "label": f"{s['course_name']} ({', '.join(s['cohorts'])})",
                      "size": campus.session_size(s), "types": ("lab",) if is_lab else ("classroom", "auditorium"), "lab_type": s.get("lab_type") if is_lab else None,
                      "need": equipment_need(campus, s, room) if is_lab else {}, "date": w["date"], "weekday": s["day"], "start": s["start"], "dur": s["duration"],
                      "faculty_id": s["faculty_id"], "cohorts": s["cohorts"], "orig_room": s["room_id"], "priority": 2 if is_lab else 1, "dept_id": s["dept_id"],
                      "code": s["course_code"], "mode": None, "slot_label": _slot(w["date"], s["start"], s["duration"])})
    for e in internal["exams_w"]:
        d = parse_date(e["date"])
        room = campus.rooms[e["room_id"]]
        types = {"theory": ("exam_hall",), "practical": ("lab",), "online": ("lab",)}[e["mode"]]
        tasks.append({"key": f"{e['id']}@{d}", "id": e["id"], "type": "exam", "kind": e["mode"], "label": f"{e['course_name']} exam ({', '.join(e['cohorts'])})",
                      "size": campus.exam_size(e), "types": types, "lab_type": room.get("lab_type") if e["mode"] != "theory" else None,
                      "need": equipment_need(campus, e, room) if room["room_type"] == "lab" else {}, "date": d, "weekday": d.weekday(), "start": e["start"], "dur": e["duration"],
                      "faculty_id": None, "cohorts": e["cohorts"], "orig_room": e["room_id"], "priority": 3, "dept_id": e["dept_id"], "code": None, "mode": e["mode"],
                      "slot_label": _slot(d, e["start"], e["duration"])})
    for v in internal["events_w"]:
        d = parse_date(v["date"])
        room = campus.rooms.get(v.get("venue_id") or "")