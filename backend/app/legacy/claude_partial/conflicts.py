"""Conflict detection engine. Works purely from the campus data (no hardcoded warnings)."""
import math
from collections import defaultdict
from itertools import combinations

from .campus import Campus, Occupancy, overlap, parse_date, DAYS, START_HOURS, fmt_hour

SEV_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


def _slot(s):
    return f"{DAYS[s['day']]} {fmt_hour(s['start'])}-{fmt_hour(s['start'] + s['duration'])}"


def equipment_need(campus, item, room):
    """Equipment units required for a lab session/exam in `room` (None if not a lab user)."""
    per = item.get("equip_per_student")
    if not per and room and room.get("lab_type") and item.get("mode") in ("practical", "online"):
        per = {"pc": 1} if room["lab_type"] == "computing" else {}
        if item.get("mode") == "practical":
            from ..services.seed_data import EQUIP_PER_STUDENT
            per = EQUIP_PER_STUDENT.get(room["lab_type"], {})
    size = campus.size(item.get("cohorts"))
    return {k: math.ceil(v * size) for k, v in (per or {}).items()}


def room_fits(campus, room, size, need=None, lab_type=None):
    if room["capacity"] < size:
        return False
    if lab_type and room.get("lab_type") != lab_type:
        return False
    for k, v in (need or {}).items():
        if (room.get("equipment") or {}).get(k, 0) < v:
            return False
    return True


def suggest_room(campus, occ, item, exclude_room, weekday=None, on_date=None, ignore=()):
    """First real alternative room: right type, capacity, equipment and free at that time."""
    size = campus.size(item.get("cohorts"))
    cur = campus.rooms.get(item["room_id"])
    types = {"classroom": ("classroom", "auditorium"), "lab": ("lab",), "exam_hall": ("exam_hall",)}.get(cur["room_type"] if cur else "classroom", ("classroom",))
    if item.get("kind") == "lecture":
        types = ("classroom", "auditorium")
    need = equipment_need(campus, item, cur) if cur and cur["room_type"] == "lab" else {}
    cands = []
    for r in campus.rooms.values():
        if r["id"] == exclude_room or r["room_type"] not in types:
            continue
        if not room_fits(campus, r, size, need, item.get("lab_type") if cur and cur["room_type"] == "lab" else None):
            continue
        if occ.room_busy(r["id"], on_date, weekday, item["start"], item.get("duration") or 1, ignore=ignore):
            continue
        cands.append((r["capacity"] - size, r["id"], r))
    cands.sort(key=lambda x: (x[0], x[1]))
    return cands[0][2] if cands else None


def suggest_faculty(campus, occ, session, exclude=()):
    code = session["course_code"]
    best = None
    for f in campus.faculty.values():
        if f["id"] in exclude or f["id"] == session["faculty_id"] or code not in f["expertise"]:
            continue
        if campus.faculty_unavailable(f["id"], session["day"], session["start"], session["duration"]):
            continue
        if occ.faculty_busy(f["id"], None, session["day"], session["start"], session["duration"], ignore={session["id"]}):
            continue
        load = campus.faculty_load(f["id"])
        if load + session["duration"] > f["max_load_hours"]:
            continue
        if best is None or load < best[0]:
            best = (load, f)