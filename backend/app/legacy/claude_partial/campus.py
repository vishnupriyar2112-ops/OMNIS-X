"""In-memory campus model used by every engine.

The engines never touch the database directly. The service layer loads rows into a
plain dict ("snapshot") and wraps it in :class:`Campus`. This keeps the algorithms
unit-testable and independent from FastAPI/SQLAlchemy.
"""
from collections import defaultdict
from datetime import date, datetime, timedelta

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]
WORK_START, WORK_END = 9, 17
LUNCH_HOUR = 13
START_HOURS = [9, 10, 11, 12, 14, 15, 16]


def overlap(s1, d1, s2, d2):
    """True when [s1, s1+d1) and [s2, s2+d2) intersect."""
    return s1 < s2 + d2 and s2 < s1 + d1


def parse_date(value):
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


def fmt_hour(h):
    return f"{int(h):02d}:00"


class Campus:
    def __init__(self, data):
        self.data = data
        self.departments = {d["id"]: d for d in data["departments"]}
        self.faculty = {f["id"]: f for f in data["faculty"]}
        self.students = {s["id"]: s for s in data["students"]}
        self.rooms = {r["id"]: r for r in data["rooms"]}
        self.nodes = {n["id"]: n for n in data["resources"]}
        self.edges = data["dependencies"]
        self.sessions = data["sessions"]
        self.exams = data["exams"]
        self.events = data["events"]
        self.cohorts = defaultdict(list)
        for s in data["students"]:
            self.cohorts[f"{s['dept_id']}-{s['year']}"].append(s["id"])

    # ---- people -------------------------------------------------------
    def students_of(self, cohorts):
        out = set()
        for c in cohorts or []:
            out.update(self.cohorts.get(c, []))
        return out

    def size(self, cohorts):
        return len(self.students_of(cohorts))

    def session_size(self, s):
        return self.size(s.get("cohorts"))

    def exam_size(self, e):
        return self.size(e.get("cohorts"))

    def faculty_load(self, faculty_id, sessions=None):
        sessions = self.sessions if sessions is None else sessions
        return sum(s["duration"] for s in sessions if s["faculty_id"] == faculty_id)

    # ---- time ---------------------------------------------------------
    def faculty_unavailable(self, faculty_id, weekday, start, dur, on_date=None):
        f = self.faculty.get(faculty_id)
        if not f:
            return False
        for u in f.get("unavailable") or []:
            if u.get("date") and on_date and str(on_date) != u["date"]:
                continue
            if u.get("date") is None and u.get("day") != weekday:
                continue
            if overlap(start, dur, u.get("from", 0), u.get("to", 24) - u.get("from", 0)):
                return True
        return False

    def rooms_of_type(self, *types):
        return [r for r in self.rooms.values() if r["room_type"] in types]

    # ---- upcoming dates ----------------------------------------------
    def default_incident_date(self, today=None):
        today = today or date.today()