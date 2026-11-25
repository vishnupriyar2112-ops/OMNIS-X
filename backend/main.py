import csv
import json
from datetime import date, datetime
from io import StringIO
from typing import Optional

import networkx as nx
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.engines.conflicts import check_event_booking, detect_conflicts
from app.engines.dependency import AVAILABLE, build_graph
from app.engines.scheduling import faculty_replacements, room_replacements
from app.models.models import (
    CampusNode, Department, Dependency, Event, Examination, FailureScenario,
    Faculty, Hostel, Incident, Resource, Room, Service, Student,
    TimetableAssignmentOverride, TimetableSession, TransportRoute,
    TransportRouteAssignmentOverride, User,
)
from app.services.analytics import dashboard_data, resource_optimization, risk_data
from app.services.auth import bearer, issue_token, require_user, verify_password
from app.services.campus_analysis import resolve_incident, simulate
from app.services.recovery_engine import recovery_data
from database import get_db
from seed import seed

seed()

app = FastAPI(title="OMNIS-X Institutional Digital Twin", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|[\d.]+):5173",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class SimulationRequest(BaseModel):
    root_node_ids: list[str] = Field(default_factory=list, max_length=20)
    scenario_id: Optional[str] = None
    duration_minutes: int = Field(default=120, ge=1, le=10080)
    starts_at: datetime = Field(default_factory=datetime.now)


class IncidentRequest(BaseModel):
    failure_type: str = Field(min_length=1, max_length=120)
    failed_node_id: str = Field(min_length=1, max_length=80)
    duration_minutes: int = Field(default=0, ge=0, le=10080)
    severity: str = Field(default="MEDIUM", pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$")
    resolution_summary: str = Field(default="", max_length=2000)


class EventBookingRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    event_date: date
    start_time: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    duration_hours: float = Field(gt=0, le=24)
    venue_id: str = Field(min_length=1, max_length=80)
    organizing_department_id: Optional[str] = Field(default=None, max_length=80)


class SessionAssignmentRequest(BaseModel):
    room_id: Optional[str] = Field(default=None, min_length=1, max_length=80)
    faculty_id: Optional[str] = Field(default=None, min_length=1, max_length=80)


class TransportTransferRequest(BaseModel):
    target_route_id: str = Field(min_length=1, max_length=80)
    rider_count: int = Field(ge=1)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
):
    return require_user(credentials, db)


def require_admin(user: User = Depends(get_current_user)):
    if user.role != "administrator":
        raise HTTPException(status_code=403, detail="Administrator role required")
    return user


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/auth/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return {
        "token": issue_token(user),
        "user": {"name": user.name, "email": user.email, "role": user.role},
    }


@app.get("/api/dashboard")
def dashboard(_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return dashboard_data(db)


@app.get("/api/twin")
def twin(_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    departments = db.query(Department).order_by(Department.id).all()
    rooms = db.query(Room).order_by(Room.id).all()
    nodes = db.query(CampusNode).order_by(CampusNode.id).all()
    services = {item.node_id: item for item in db.query(Service).all()}
    resources = {item.node_id: item for item in db.query(Resource).all()}
    hostels = db.query(Hostel).order_by(Hostel.id).all()
    routes = db.query(TransportRoute).order_by(TransportRoute.id).all()
    exam_halls = [room for room in rooms if room.kind == "exam_hall"]
    department_data = []
    for item in departments:
        department_rooms = [room for room in rooms if room.department_id == item.id]
        available_rooms = sum(room.status in AVAILABLE for room in department_rooms)
        department_data.append({
            "id": item.id, "name": item.name,
            "students": db.query(Student).filter(
                Student.department_id == item.id, Student.status == "active"
            ).count(),
            "faculty": db.query(Faculty).filter(Faculty.department_id == item.id).count(),
            "available_rooms": available_rooms, "total_rooms": len(department_rooms),
            "health": round(100 * available_rooms / len(department_rooms)) if department_rooms else 100,
            "data_status": item.data_status,
        })
    return {
        "departments": department_data,
        "rooms": [{
            "id": room.id, "name": room.id, "building": room.building, "kind": room.kind,
            "capacity": room.capacity, "status": room.status, "department": room.department_id,
            "lab_type": room.lab_type, "equipment": room.equipment,
        } for room in rooms],
        "resources": [{
            "id": node.id, "name": node.name, "kind": node.node_type,
            "resource_type": resources[node.id].resource_type if node.id in resources else None,
            "service_type": services[node.id].service_type if node.id in services else None,
            "status": node.status, "criticality": node.criticality_label,
        } for node in nodes],
        "facilities": {
            "transport_routes": len(routes),
            "hostels": len(hostels),
            "hostel_beds": sum(hostel.capacity for hostel in hostels),
            "examination_halls": len(exam_halls),
        },
        "data_status": "synthetic_demo",
    }


@app.get("/api/resources")
def resources(_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    nodes = db.query(CampusNode).order_by(CampusNode.node_type, CampusNode.name).all()
    return {"resources": [{
        "id": node.id, "name": node.name, "type": node.node_type,
        "status": node.status, "criticality": node.criticality_label,
    } for node in nodes]}


@app.get("/api/dependency")
def dependency(_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    graph, _ = build_graph(db)
    layers = {}
    for level, nodes in enumerate(nx.topological_generations(graph)):
        for node in nodes:
            layers[node] = level
    return {
        "nodes": [{
            "id": node_id, **attrs, "layer": layers[node_id],
            "direct_dependents": graph.out_degree(node_id),
            "downstream_nodes": len(nx.descendants(graph, node_id)),
        } for node_id, attrs in graph.nodes(data=True)],
        "edges": [{
            "id": attrs["id"], "source": source, "target": target,
            "kind": attrs["kind"], "weight": attrs["weight"],
            "mitigation_resource_id": attrs["mitigation_resource_id"],
        } for source, target, attrs in graph.edges(data=True)],
        "single_points_of_failure": [
            node_id for node_id in graph.nodes
            if graph.out_degree(node_id) and not all(
                attrs.get("mitigation_resource_id")
                and db.get(Resource, attrs["mitigation_resource_id"])
                and db.get(Resource, attrs["mitigation_resource_id"]).backup_available
                and db.get(Resource, attrs["mitigation_resource_id"]).node.status in AVAILABLE
                for _, _, attrs in graph.out_edges(node_id, data=True)
            )
        ],
    }


@app.get("/api/conflicts")
def conflicts(_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    found = detect_conflicts(db)
    return {"conflicts": found, "count": len(found), "source": "synthetic_demo timetable"}


@app.post("/api/events/check")
def check_event(
    payload: EventBookingRequest,
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    found = check_event_booking(
        db, payload.name, payload.event_date, payload.start_time,
        payload.duration_hours, payload.venue_id, payload.organizing_department_id,
    )
    return {"can_schedule": not found, "conflicts": found}


@app.post("/api/conflicts/{conflict_id}/auto-fix")
def apply_conflict_fix(
    conflict_id: str,
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    issue = next((item for item in detect_conflicts(db) if item["id"] == conflict_id), None)
    if issue is None:
        raise HTTPException(status_code=404, detail="Conflict is no longer present")
    fix = issue.get("auto_fix")
    if not fix:
        raise HTTPException(status_code=409, detail="This finding has no safe automatic fix")

    activity_id = fix.get("session_id")
    session = db.get(TimetableSession, activity_id) if activity_id else None
    exam_id = fix.get("exam_id")
    exam = db.get(Examination, exam_id) if exam_id else None
    room_id = fix.get("room_id")
    faculty_id = fix.get("faculty_id")
    sessions = db.query(TimetableSession).filter(TimetableSession.status == "scheduled").all()

    if fix["kind"] == "room":
        if session:
            source_room = db.get(Room, session.room_id)
            kind = (
                "laboratory"
                if "lab" in session.session_type.lower() or "practical" in session.session_type.lower()
                else "classroom"
            )
            candidates = room_replacements(
                db, source_room, session.expected_students, kind, session.weekday,
                session.start_time, session.duration_hours, sessions,
                skip_session_id=session.id, department_id=session.department_id,
            )
            target = session
        elif exam:
            source_room = db.get(Room, exam.room_id)
            candidates = room_replacements(
                db, source_room, exam.student_count, "exam_hall",
                exam.exam_date.strftime("%a"), exam.start_time, exam.duration_hours,
                sessions, event_date=exam.exam_date,
            )
            target = exam
        else:
            raise HTTPException(status_code=409, detail="The scheduled activity no longer exists")
        if not any(item["id"] == room_id for item in candidates):
            raise HTTPException(status_code=409, detail="The suggested room is no longer available")
        target.room_id = room_id
    elif fix["kind"] == "faculty" and session:
        candidates = faculty_replacements(db, session, sessions)
        if not any(item["id"] == faculty_id for item in candidates):
            raise HTTPException(status_code=409, detail="The suggested faculty member is no longer available")
        session.faculty_id = faculty_id
    else:
        raise HTTPException(status_code=409, detail="Unsupported automatic fix")

    db.flush()
    if any(item["id"] == conflict_id for item in detect_conflicts(db)):
        db.rollback()
        raise HTTPException(status_code=409, detail="The proposed change did not resolve this conflict")
    if session is not None:
        override = db.get(TimetableAssignmentOverride, session.id)
        if override is None:
            db.add(TimetableAssignmentOverride(
                session_id=session.id, room_id=session.room_id, faculty_id=session.faculty_id,
            ))
        else:
            override.room_id = session.room_id
            override.faculty_id = session.faculty_id
    db.commit()
    return {"resolved": True, "conflict_id": conflict_id, "activity_id": activity_id or exam_id}


def _session_room_kind(session):
    if "lab" in session.session_type.lower() or "practical" in session.session_type.lower():
        return "laboratory"
    return "classroom"


@app.get("/api/assignments")
def assignments(_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    sessions = db.query(TimetableSession).filter(
        TimetableSession.status == "scheduled"
    ).order_by(
        TimetableSession.weekday, TimetableSession.start_time, TimetableSession.id,
    ).all()
    routes = db.query(TransportRoute).order_by(TransportRoute.route_name).all()
    return {
        "sessions": [{
            "id": item.id, "course_code": item.course_code, "session_type": item.session_type,
            "department_id": item.department_id, "weekday": item.weekday,
            "start_time": item.start_time, "duration_hours": item.duration_hours,
            "expected_students": item.expected_students, "room_id": item.room_id,
            "faculty_id": item.faculty_id,
        } for item in sessions],
        "routes": [{
            "id": item.id, "bus_id": item.bus_id, "route_name": item.route_name,
            "daily_capacity": item.daily_capacity, "assigned_students": item.assigned_students,
            "spare_seats": max(item.daily_capacity - item.assigned_students, 0),
        } for item in routes],
    }


@app.get("/api/assignments/sessions/{session_id}/options")
def assignment_options(
    session_id: str,
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    session = db.get(TimetableSession, session_id)
    if session is None or session.status != "scheduled":
        raise HTTPException(status_code=404, detail="Scheduled class or lab not found")
    sessions = db.query(TimetableSession).filter(
        TimetableSession.status == "scheduled"
    ).all()
    room = db.get(Room, session.room_id)
    rooms = room_replacements(
        db, room, session.expected_students, _session_room_kind(session),
        session.weekday, session.start_time, session.duration_hours, sessions,
        skip_session_id=session.id, department_id=session.department_id,
    )
    faculty_options = faculty_replacements(db, session, sessions)
    return {
        "rooms": rooms,
        "faculty": faculty_options,
        "current_room_id": session.room_id,
        "current_faculty_id": session.faculty_id,
    }


@app.post("/api/assignments/sessions/{session_id}")
def assign_session(
    session_id: str,
    payload: SessionAssignmentRequest,
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if payload.room_id is None and payload.faculty_id is None:
        raise HTTPException(status_code=422, detail="Select a room, a faculty member, or both")
    session = db.get(TimetableSession, session_id)
    if session is None or session.status != "scheduled":
        raise HTTPException(status_code=404, detail="Scheduled class or lab not found")
    sessions = db.query(TimetableSession).filter(
        TimetableSession.status == "scheduled"
    ).all()
    room_changed = payload.room_id is not None and payload.room_id != session.room_id
    faculty_changed = payload.faculty_id is not None and payload.faculty_id != session.faculty_id

    if room_changed:
        room_options = room_replacements(
            db, db.get(Room, session.room_id), session.expected_students,
            _session_room_kind(session), session.weekday, session.start_time,
            session.duration_hours, sessions, skip_session_id=session.id,
            department_id=session.department_id,
        )
        if not any(item["id"] == payload.room_id for item in room_options):
            raise HTTPException(status_code=409, detail="That room is not free and compatible for this class")
        session.room_id = payload.room_id

    if faculty_changed:
        faculty_options = faculty_replacements(db, session, sessions)
        if not any(item["id"] == payload.faculty_id for item in faculty_options):
            raise HTTPException(status_code=409, detail="That faculty member is unavailable or not qualified")
        session.faculty_id = payload.faculty_id

    db.flush()
    findings = detect_conflicts(db)
    room_conflicts = {
        "capacity", "room_status", "lab_type", "room_overlap", "exam_room_overlap",
        "event_venue_overlap",
    }
    faculty_conflicts = {
        "faculty_expertise", "faculty_availability", "faculty_overlap", "invigilator_overlap",
    }
    unresolved = any(
        session.id in item["affected_entities"]
        and (
            (room_changed and item["type"] in room_conflicts)
            or (faculty_changed and item["type"] in faculty_conflicts)
        )
        for item in findings
    )
    if unresolved:
        db.rollback()
        raise HTTPException(status_code=409, detail="The assignment creates a scheduling conflict")

    override = db.get(TimetableAssignmentOverride, session.id)
    if override is None:
        db.add(TimetableAssignmentOverride(
            session_id=session.id, room_id=session.room_id, faculty_id=session.faculty_id,
        ))
    else:
        override.room_id = session.room_id
        override.faculty_id = session.faculty_id
    db.commit()
    return {"session_id": session.id, "room_id": session.room_id, "faculty_id": session.faculty_id}


@app.post("/api/transport-routes/{source_route_id}/transfer")
def transfer_route_riders(
    source_route_id: str,
    payload: TransportTransferRequest,
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    source = db.get(TransportRoute, source_route_id)
    target = db.get(TransportRoute, payload.target_route_id)
    if source is None or target is None:
        raise HTTPException(status_code=404, detail="Transport route not found")
    if source.id == target.id:
        raise HTTPException(status_code=422, detail="Choose a different destination route")
    if payload.rider_count > source.assigned_students:
        raise HTTPException(status_code=409, detail="The source route has fewer riders than requested")
    spare = max(target.daily_capacity - target.assigned_students, 0)
    if payload.rider_count > spare:
        raise HTTPException(status_code=409, detail=f"The destination route has only {spare} spare seats")

    source.assigned_students -= payload.rider_count
    target.assigned_students += payload.rider_count
    for route in (source, target):
        override = db.get(TransportRouteAssignmentOverride, route.id)
        if override is None:
            db.add(TransportRouteAssignmentOverride(
                route_id=route.id, assigned_students=route.assigned_students,
            ))
        else:
            override.assigned_students = route.assigned_students
    db.commit()
    return {
        "source_route_id": source.id, "source_assigned_students": source.assigned_students,
        "target_route_id": target.id, "target_assigned_students": target.assigned_students,
        "transferred_riders": payload.rider_count,
    }


@app.get("/api/simulations/scenarios")
def scenarios(_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"scenarios": [{
        "id": item.id, "name": item.name, "root_node_id": item.root_node_id,
        "duration_minutes": item.duration_minutes, "severity": item.severity_input,
        "description": item.assumption,
    } for item in db.query(FailureScenario).order_by(FailureScenario.id).all()]}


@app.post("/api/simulations/run")
def run_simulation(
    payload: SimulationRequest,
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    roots = payload.root_node_ids
    if payload.scenario_id:
        scenario = db.get(FailureScenario, payload.scenario_id)
        if scenario is None:
            raise HTTPException(status_code=404, detail="Failure scenario not found")
        roots = roots or [scenario.root_node_id]
        if not payload.root_node_ids:
            payload.duration_minutes = scenario.duration_minutes
    try:
        return simulate(db, roots, payload.duration_minutes, payload.starts_at)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/resource-optimization")
def optimization(_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return resource_optimization(db)


@app.get("/api/risk")
def risk(_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return risk_data(db)


@app.get("/api/incidents")
def incidents(
    status: Optional[str] = None,
    search: Optional[str] = Query(default=None, max_length=100),
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Incident)
    if status:
        query = query.filter(Incident.resolution_status == status)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            Incident.id.like(term) | Incident.failure_type.like(term) |
            Incident.failed_resource.like(term)
        )
    rows = query.order_by(Incident.timestamp.desc()).all()
    return {"incidents": [{
        "id": item.id, "failure_type": item.failure_type,
        "failed_resource": item.failed_resource, "failed_node_id": item.failed_node_id,
        "timestamp": item.timestamp.isoformat(), "duration_minutes": item.duration_minutes,
        "severity": item.severity, "impact_score": item.impact_score,
        "affected_resources": json.loads(item.affected_resources or "{}"),
        "recovery_plan": item.recovery_plan, "resolution_summary": item.resolution_summary,
        "restored_at": item.restored_at.isoformat() if item.restored_at else None,
        "resolution_status": item.resolution_status, "is_synthetic": item.is_synthetic,
    } for item in rows]}


@app.post("/api/incidents")
def create_incident(
    payload: IncidentRequest,
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    node = db.get(CampusNode, payload.failed_node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="Campus node not found")
    incident = Incident(
        id=f"INC-MANUAL-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
        failure_type=payload.failure_type, failed_resource=node.name, failed_node_id=node.id,
        timestamp=datetime.now(), duration_minutes=payload.duration_minutes,
        severity=payload.severity, impact_score=0, affected_resources=json.dumps({}),
        recovery_plan="", resolution_summary=payload.resolution_summary,
        resolution_status="Open", is_synthetic=False,
    )
    db.add(incident)
    db.commit()
    return {"id": incident.id, "status": incident.resolution_status}


@app.post("/api/incidents/{incident_id}/resolve")
def resolve(
    incident_id: str,
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    resolve_incident(db, incident)
    return {"id": incident.id, "status": incident.resolution_status}


@app.get("/api/incidents/export")
def export_incidents(_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Incident ID", "Failure Type", "Failed Resource", "Timestamp", "Duration Minutes",
        "Severity", "Impact Score", "Status", "Resolution Summary",
    ])
    for incident in db.query(Incident).order_by(Incident.timestamp.desc()).all():
        writer.writerow([
            incident.id, incident.failure_type, incident.failed_resource, incident.timestamp.isoformat(),
            incident.duration_minutes, incident.severity, incident.impact_score,
            incident.resolution_status, incident.resolution_summary,
        ])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=omnisx-incidents.csv"},
    )


@app.get("/api/recovery")
def recovery(
    incident_id: Optional[str] = None,
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not incident_id:
        incident = db.query(Incident).filter(
            Incident.resolution_status != "Resolved"
        ).order_by(Incident.timestamp.desc()).first()
        if incident is None:
            raise HTTPException(status_code=404, detail="Run a simulation before requesting recovery plans")
        incident_id = incident.id
    try:
        return recovery_data(db, incident_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
