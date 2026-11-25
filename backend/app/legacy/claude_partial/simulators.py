"""Failure simulation orchestration + Failure Impact Score."""
from datetime import datetime, timedelta, date

from ..engines.campus import Campus, overlap, parse_date, WORK_START, WORK_END, DAYS
from ..engines.dependency import DependencyEngine
from .cascade import propagate, critical_chain, FAILED_STATES

SCENARIOS = [
    {"id": "electricity", "name": "Main electricity failure", "roots": ["PWR_GRID"], "icon": "zap",
     "description": "Utility feeder trips. Only essential loads (core network, ERP, exam halls, water pump) move to the generator."},
    {"id": "internet", "name": "Campus internet failure", "roots": ["NET_ISP"], "icon": "wifi-off",
     "description": "ISP fibre link goes down. Internal LAN survives; cloud-dependent services fail."},
    {"id": "computer_lab", "name": "Computer laboratory failure", "roots": ["LAB_CSE1"], "icon": "monitor",
     "description": "Computer Lab 1 becomes unusable (AC / network switch fault)."},
    {"id": "faculty", "name": "Faculty unavailability", "roots": ["FAC_CSE_05"], "icon": "user-x",
     "description": "A heavily-loaded CSE faculty member is unavailable for the day."},
    {"id": "transport", "name": "Transportation breakdown", "roots": ["BUS_2"], "icon": "bus",
     "description": "Bus 2 (East route) breaks down."},
    {"id": "hostel_water", "name": "Hostel water supply failure", "roots": ["WATER_SUPPLY"], "icon": "droplets",
     "description": "Municipal water supply is interrupted; tanks buffer for about two hours."},
    {"id": "exam_hall", "name": "Examination hall unavailable", "roots": ["EH_A"], "icon": "building",
     "description": "Examination Hall A (80 seats) is closed (structural / ceiling issue)."},
    {"id": "placement", "name": "Placement infrastructure failure", "roots": ["SYS_PLACE_PORTAL", "PLC_HALL"], "icon": "briefcase",
     "description": "Placement portal and interview rooms are both unavailable on a drive day."},
]

IMPACT_WEIGHTS = {"resources": 0.20, "departments": 0.15, "students": 0.25, "faculty": 0.10, "criticality": 0.20, "duration": 0.10}
SEVERITY_BANDS = [(25, "LOW"), (50, "MEDIUM"), (75, "HIGH"), (101, "CRITICAL")]


def severity_of(score):
    for limit, name in SEVERITY_BANDS:
        if score < limit:
            return name
    return "CRITICAL"


def build_windows(on_date, start_hour, duration_hours):
    """Working-hour exposure windows (09:00-17:00, Mon-Fri) covered by the outage."""
    t0 = datetime(on_date.year, on_date.month, on_date.day, int(start_hour))
    t1 = t0 + timedelta(hours=float(duration_hours))
    out, d = [], t0.date()
    while d <= t1.date() and len(out) < 10:
        if d.weekday() < 5:
            ds = datetime(d.year, d.month, d.day)
            h0 = max(WORK_START, (t0 - ds).total_seconds() / 3600)
            h1 = min(WORK_END, (t1 - ds).total_seconds() / 3600)
            h0, h1 = int(h0), int(-(-h1 // 1))
            if h1 > h0:
                out.append({"date": d, "weekday": d.weekday(), "h0": h0, "h1": h1})
        d += timedelta(days=1)
    return out


def in_windows(windows, weekday=None, on_date=None, start=0, dur=1):
    for w in windows:
        if weekday is not None and w["weekday"] != weekday:
            continue
        if on_date is not None and str(w["date"]) != str(on_date):
            continue
        if overlap(start, dur, w["h0"], w["h1"] - w["h0"]):
            return True