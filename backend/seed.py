import csv
import hashlib
import json
import secrets
import sqlite3
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import inspect, text

from database import Base, DB_PATH, SessionLocal, engine
from app.models.models import (
    CampusNode, Department, Dependency, Event, Examination, Faculty, FailureScenario,
    Hostel, Incident, RecoveryOption, Resource, Room, Service, Student,
    TimetableAssignmentOverride, TimetableSession, TransportRoute,
    TransportRouteAssignmentOverride, User,
)

DATA_DIR = Path(__file__).resolve().parent / "data" / "synthetic_dataset"
CRITICALITY = {"critical": 1.0, "high": 0.8, "medium": 0.5, "low": 0.25}


def _read(name):
    with (DATA_DIR / name).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _time(value):
    return value.strip()


def _date(value):
    return date.fromisoformat(value)


def _datetime(value):
    return datetime.fromisoformat(value)


def _bool(value):
    return value.strip().lower() in {"yes", "true", "1"}


def _hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 310_000)
    return f"pbkdf2_sha256${salt}${digest.hex()}"


def _legacy_incidents():
    if not DB_PATH.exists():
        return []
    connection = sqlite3.connect(DB_PATH)
    try:
        table = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='incidents'"
        ).fetchone()
        if not table:
            return []
        cursor = connection.execute("SELECT * FROM incidents")
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        connection.close()


def _migrate_existing_schema():
    tables = inspect(engine).get_table_names()
    if "campus_nodes" in tables:
        if "events" in tables and "organizing_department_id" not in {
            column["name"] for column in inspect(engine).get_columns("events")
        }:
            with engine.begin() as connection:
                connection.execute(text(
                    "ALTER TABLE events ADD COLUMN organizing_department_id VARCHAR"
                ))
        return []
    legacy = _legacy_incidents()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    return legacy


def _upsert(db, model, key, values):
    record = db.get(model, key)
    if record is None:
        record = model(**values)
        db.add(record)
    else:
        for field, value in values.items():
            if field not in ("id", "node_id"):
                setattr(record, field, value)
    return record


def _import_dataset(db):
    for row in _read("departments.csv"):
        _upsert(db, Department, row["department_id"], {
            "id": row["department_id"], "name": row["department_name"],
            "student_count": int(row["student_count"]), "faculty_count": int(row["faculty_count"]),
            "academic_years": row["academic_years"], "data_status": row["data_status"],
        })

    for row in _read("students.csv"):
        _upsert(db, Student, row["student_id"], {
            "id": row["student_id"], "department_id": row["department_id"],
            "year": int(row["year"]), "semester": int(row["semester"]),
            "cohort_id": row["cohort_id"], "status": row["status"],
            "data_status": row["data_status"],
        })

    for row in _read("faculty.csv"):
        _upsert(db, Faculty, row["faculty_id"], {
            "id": row["faculty_id"], "department_id": row["department_id"],
            "designation": row["designation"], "expertise_course_codes": row["expertise_course_codes"],
            "max_weekly_hours": int(row["max_weekly_hours"]),
            "availability_status": row["availability_status"], "data_status": row["data_status"],
        })

    for row in _read("resources.csv"):
        label = row["criticality"].lower()
        _upsert(db, CampusNode, row["resource_id"], {
            "id": row["resource_id"], "name": row["resource_name"], "node_type": "resource",
            "criticality": CRITICALITY.get(label, 0.5), "criticality_label": label,
            "status": row["status"], "data_status": row["data_status"],
        })
        _upsert(db, Resource, row["resource_id"], {
            "node_id": row["resource_id"], "resource_type": row["resource_type"],
            "zone_id": row["zone_id"], "backup_available": _bool(row["backup_available"]),
        })

    for row in _read("services.csv"):
        label = row["criticality"].lower()
        _upsert(db, CampusNode, row["node_id"], {
            "id": row["node_id"], "name": row["node_name"], "node_type": "service",
            "criticality": CRITICALITY.get(label, 0.5), "criticality_label": label,
            "status": row["status"], "data_status": row["data_status"],
        })
        _upsert(db, Service, row["node_id"], {
            "node_id": row["node_id"], "service_type": row["node_type"],
        })

    for row in _read("dependencies.csv"):
        mitigation = row["mitigation_resource_id"] or None
        _upsert(db, Dependency, row["dependency_id"], {
            "id": row["dependency_id"], "source_node_id": row["source_node_id"],
            "target_node_id": row["target_node_id"], "dependency_type": row["dependency_type"],
            "weight": float(row["weight"]), "mitigation_resource_id": mitigation,
            "direction_note": row["direction_note"],
        })

    for row in _read("rooms.csv"):
        _upsert(db, Room, row["room_id"], {
            "id": row["room_id"], "building": row["building"], "kind": row["room_type"],
            "capacity": int(row["capacity"]), "department_id": row["department_id"] or None,
            "lab_type": row["lab_type"], "equipment": row["equipment"],
            "power_zone": row["power_zone"], "network_zone": row["network_zone"],
            "status": row["status"], "data_status": "synthetic_demo",
        })

    for row in _read("timetable_sessions.csv"):
        _upsert(db, TimetableSession, row["session_id"], {
            "id": row["session_id"], "cohort_id": row["cohort_id"],
            "department_id": row["department_id"], "course_code": row["course_code"],
            "session_type": row["session_type"], "room_id": row["room_id"],
            "faculty_id": row["faculty_id"], "weekday": row["weekday"],
            "start_time": _time(row["start_time"]), "duration_hours": float(row["duration_hours"]),
            "expected_students": int(row["expected_students"]), "status": row["status"],
            "data_status": "synthetic_demo",
        })

    for row in _read("examinations.csv"):
        _upsert(db, Examination, row["exam_id"], {
            "id": row["exam_id"], "cohort_id": row["cohort_id"],
            "department_id": row["department_id"], "course_code": row["course_code"],
            "exam_date": _date(row["exam_date"]), "start_time": _time(row["start_time"]),
            "duration_hours": float(row["duration_hours"]), "room_id": row["room_id"],
            "student_count": int(row["student_count"]), "invigilator_id": row["invigilator_id"],
            "exam_mode": row["exam_mode"], "status": row["status"], "data_status": "synthetic_demo",
        })

    for row in _read("hostels.csv"):
        _upsert(db, Hostel, row["hostel_id"], {
            "id": row["hostel_id"], "capacity": int(row["capacity"]), "occupied": int(row["occupied"]),
            "water_zone": row["water_zone"], "power_zone": row["power_zone"],
            "backup_hours": float(row["backup_hours"]), "data_status": "synthetic_demo",
        })

    for row in _read("transport_routes.csv"):
        _upsert(db, TransportRoute, row["route_id"], {
            "id": row["route_id"], "bus_id": row["bus_id"], "route_name": row["route_name"],
            "daily_capacity": int(row["daily_capacity"]), "assigned_students": int(row["assigned_students"]),
            "arrival_buffer_minutes": int(row["arrival_buffer_minutes"]), "data_status": "synthetic_demo",
        })

    for row in _read("events.csv"):
        _upsert(db, Event, row["event_id"], {
            "id": row["event_id"], "name": row["event_name"], "event_type": row["event_type"],
            "organizing_department_id": row.get("organizing_department_id") or None,
            "event_date": _date(row["date"]), "start_time": _time(row["start_time"]),
            "duration_hours": float(row["duration_hours"]), "venue_id": row["venue_id"],
            "priority": row["priority"], "data_status": "synthetic_demo",
        })

    for row in _read("failure_scenarios.csv"):
        _upsert(db, FailureScenario, row["scenario_id"], {
            "id": row["scenario_id"], "name": row["name"], "root_node_id": row["root_node_id"],
            "duration_minutes": int(row["duration_minutes"]), "severity_input": row["severity_input"],
            "assumption": row["assumption"],
        })

    for row in _read("recovery_options.csv"):
        required_id = row["required_resource_id"]
        _upsert(db, RecoveryOption, row["option_id"], {
            "id": row["option_id"], "scenario_family": row["scenario_family"],
            "action": row["action"], "required_resource_id": required_id,
            "required_node_id": required_id if db.get(CampusNode, required_id) else None,
            "required_room_id": required_id if db.get(Room, required_id) else None,
            "capacity_limit": row["capacity_limit"],
            "estimated_setup_minutes": int(row["estimated_setup_minutes"]),
            "direct_cost_units": float(row["direct_cost_units"]),
            "disruption_level": row["disruption_level"],
        })

    for row in _read("incident_history.csv"):
        failed_node_id = row["failed_node_id"]
        if db.get(CampusNode, failed_node_id) is None:
            failed_node_id = None
        _upsert(db, Incident, row["incident_id"], {
            "id": row["incident_id"], "failure_type": row["incident_type"],
            "failed_resource": row["failed_node_id"], "failed_node_id": failed_node_id,
            "timestamp": _datetime(row["start_timestamp"]),
            "duration_minutes": int(row["duration_minutes"]), "severity": row["severity"],
            "impact_score": 0, "affected_resources": "[]", "recovery_plan": "",
            "resolution_summary": row["resolution_summary"], "resolution_status": "Resolved",
            "is_synthetic": _bool(row["is_synthetic"]),
        })

    account = db.query(User).filter(User.email == "admin@omnisx.com").first()
    if account is None:
        db.add(User(email="admin@omnisx.com", name="Campus Administrator",
                    password_hash=_hash_password("Omnis@123"), role="administrator"))
    db.flush()


def _apply_operational_overrides(db):
    for override in db.query(TimetableAssignmentOverride).all():
        session = db.get(TimetableSession, override.session_id)
        if session is not None:
            session.room_id = override.room_id
            session.faculty_id = override.faculty_id
    for override in db.query(TransportRouteAssignmentOverride).all():
        route = db.get(TransportRoute, override.route_id)
        if route is not None:
            route.assigned_students = override.assigned_students


def seed():
    legacy = _migrate_existing_schema()
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        _import_dataset(db)
        _apply_operational_overrides(db)
        for old in legacy:
            incident_id = str(old.get("id") or "")
            if not incident_id or db.get(Incident, incident_id):
                continue
            affected = old.get("affected_resources") or "[]"
            try:
                json.loads(affected)
            except (TypeError, json.JSONDecodeError):
                affected = json.dumps([part.strip() for part in affected.split(",") if part.strip()])
            failed = str(old.get("failed_resource") or "Unknown")
            db.add(Incident(
                id=incident_id, failure_type=str(old.get("failure_type") or "Legacy incident"),
                failed_resource=failed, failed_node_id=failed if db.get(CampusNode, failed) else None,
                timestamp=datetime.fromisoformat(str(old.get("timestamp") or datetime.now().isoformat())),
                duration_minutes=int(old.get("duration_minutes") or 0),
                severity=str(old.get("severity") or "MEDIUM"),
                impact_score=float(old.get("impact_score") or 0), affected_resources=affected,
                recovery_plan=str(old.get("recovery_plan") or ""),
                resolution_summary="", resolution_status=str(old.get("resolution_status") or "Resolved"),
                is_synthetic=True,
            ))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
