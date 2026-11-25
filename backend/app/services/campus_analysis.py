import json
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import func

from app.engines.dependency import FAILED, critical_chain, propagate
from app.models.models import (
    CampusNode, Department, Event, Examination, Faculty, Hostel, Incident,
    Resource, Room, Student, TimetableSession, TransportRoute,
)


def _hour(value):
    hours, minutes = value.split(":")
    return int(hours) + int(minutes) / 60


def _overlap(start_a, duration_a, start_b, duration_b):
    return start_a < start_b + duration_b and start_b < start_a + duration_a


def _matching_activities(db, starts_at, duration_minutes, bad_rooms, affected_service_ids):
    weekday = starts_at.strftime("%a")
    start_hour = starts_at.hour + starts_at.minute / 60
    duration = duration_minutes / 60
    sessions = []
    for session in db.query(TimetableSession).filter(TimetableSession.status == "scheduled").all():
        if session.weekday[:3].title() != weekday:
            continue
        if not _overlap(start_hour, duration, _hour(session.start_time), session.duration_hours):
            continue
        if session.room_id not in bad_rooms:
            continue
        sessions.append(session)

    examinations = []
    for exam in db.query(Examination).filter(Examination.status == "scheduled").all():
        if exam.exam_date != starts_at.date():
            continue
        if not _overlap(start_hour, duration, _hour(exam.start_time), exam.duration_hours):
            continue
        if exam.room_id in bad_rooms or any("EXAM" in service_id for service_id in affected_service_ids):
            examinations.append(exam)

    events = []
    for event in db.query(Event).all():
        if event.event_date != starts_at.date() or event.venue_id not in bad_rooms:
            continue
        if _overlap(start_hour, duration, _hour(event.start_time), event.duration_hours):
            events.append(event)
    return sessions, examinations, events


def _rooms_for_nodes(db, node_ids):
    rooms = {room.id: room for room in db.query(Room).all()}
    departments = {department.id for department in db.query(Department).all()}
    bad_rooms = {node_id for node_id in node_ids if node_id in rooms}
    for node_id in node_ids:
        normalized = node_id.upper()
        if "LAB" in normalized:
            department_id = next((dep for dep in departments if dep in normalized), None)
            if department_id:
                bad_rooms.update(
                    room.id for room in rooms.values()
                    if room.department_id == department_id and room.kind == "laboratory"
                )
    return bad_rooms


def simulate(db, root_ids, duration_minutes, starts_at):
    if not root_ids:
        raise ValueError("Select at least one resource or service to fail.")
    if len(set(root_ids)) != len(root_ids):
        root_ids = list(dict.fromkeys(root_ids))
    graph, resources, state, triggers, mitigated, waves = propagate(db, root_ids, duration_minutes)
    active_roots = set(root_ids) | {
        node_id for node_id, status in state.items() if status in FAILED and node_id not in triggers
    }
    node_rows = {node.id: node for node in db.query(CampusNode).all()}
    affected_node_ids = sorted(node_id for node_id, status in state.items() if status in FAILED | {"degraded"})
    affected_services = {
        node_id for node_id in affected_node_ids if graph.nodes[node_id]["type"] == "service"
    }
    bad_rooms = _rooms_for_nodes(db, affected_node_ids)
    for node_id in affected_node_ids:
        resource = resources.get(node_id)
        if resource and resource.resource_type in ("electricity", "backup_power"):
            zone_rooms = {
                room.id for room in db.query(Room).filter(
                    Room.power_zone == resource.zone_id
                ).all()
            }
            if node_id in root_ids and any(
                item["from"] == node_id and item["status"] != "mitigated"
                for item in mitigated
            ):
                bad_rooms.update(zone_rooms)

    sessions, examinations, events = _matching_activities(
        db, starts_at, duration_minutes, bad_rooms, affected_services
    )
    cohorts = {item.cohort_id for item in sessions} | {item.cohort_id for item in examinations}
    student_count = db.query(Student).filter(
        Student.status == "active", Student.cohort_id.in_(cohorts)
    ).count() if cohorts else 0
    faculty_ids = {item.faculty_id for item in sessions}
    faculty_ids.update(item.invigilator_id for item in examinations)
    total_students = db.query(Student).filter(Student.status == "active").count()
    total_faculty = db.query(Faculty).count()
    total_nodes = len(graph.nodes)
    total_rooms = db.query(Room).count()
    affected_rooms = sorted(bad_rooms)
    affected_routes = db.query(TransportRoute).filter(
        TransportRoute.bus_id.in_(affected_node_ids)
    ).all() if affected_node_ids else []
    affected_hostels = []
    water_zones = {
        resources[node_id].zone_id for node_id in affected_node_ids
        if node_id in resources and resources[node_id].resource_type == "water"
    }
    if water_zones or any("HOSTEL" in node_id for node_id in affected_services):
        affected_hostels = db.query(Hostel).filter(
            Hostel.water_zone.in_(water_zones)
        ).all() if water_zones else db.query(Hostel).all()
    affected_riders = sum(route.assigned_students for route in affected_routes)
    affected_residents = sum(hostel.occupied for hostel in affected_hostels)
    affected_departments = {
        item.department_id for item in sessions + examinations
    }
    affected_departments.update(
        row[0] for row in db.query(Room.department_id).filter(
            Room.id.in_(bad_rooms), Room.department_id.is_not(None)
        ).all()
    )
    exposed_nodes = len(affected_node_ids)
    exposure = {
        "students": student_count / max(total_students, 1),
        "faculty": len(faculty_ids) / max(total_faculty, 1),
        "nodes": exposed_nodes / max(total_nodes, 1),
        "rooms": len(affected_rooms) / max(total_rooms, 1),
    }
    impact_score = round(100 * sum(exposure.values()) / len(exposure))
    severity = "CRITICAL" if impact_score >= 50 else "HIGH" if impact_score >= 25 else "MEDIUM" if impact_score >= 10 else "LOW"
    chain = critical_chain(graph, active_roots, state, triggers)

    entities = {
        "nodes": affected_node_ids,
        "rooms": affected_rooms,
        "sessions": [item.id for item in sessions],
        "examinations": [item.id for item in examinations],
        "events": [item.id for item in events],
        "routes": [item.id for item in affected_routes],
        "hostels": [item.id for item in affected_hostels],
        "departments": sorted(affected_departments),
        "faculty": sorted(faculty_ids),
        "cohorts": sorted(cohorts),
    }
    incident_id = f"INC-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:6]}"
    incident = Incident(
        id=incident_id, failure_type="Simulated campus failure",
        failed_resource=", ".join(root_ids), failed_node_id=root_ids[0],
        timestamp=starts_at, duration_minutes=duration_minutes, severity=severity,
        impact_score=impact_score, affected_resources=json.dumps(entities),
        recovery_plan="", resolution_summary="",
        resolution_status="Open", is_synthetic=True,
    )
    db.add(incident)

    for node_id, status in state.items():
        if status in FAILED:
            node_rows[node_id].status = "failed" if node_id in root_ids else "degraded"
        elif status == "degraded":
            node_rows[node_id].status = "degraded"
    for room_id in affected_rooms:
        room = db.get(Room, room_id)
        if room and room.status == "operational":
            room.status = "degraded"
    db.commit()

    timeline = [
        {"node_id": node_id, "name": graph.nodes[node_id]["name"],
         "status": state[node_id], "cascade_wave": waves.get(node_id, 0),
         "triggered_by": triggers.get(node_id, [])}
        for node_id in affected_node_ids
    ]
    return {
        "incident_id": incident_id, "root_failures": root_ids,
        "duration_minutes": duration_minutes, "starts_at": starts_at.isoformat(),
        "affected_resources": affected_node_ids, "affected_entities": entities,
        "affected_students": student_count, "affected_faculty": len(faculty_ids),
        "affected_departments": sorted(affected_departments),
        "affected_laboratories": sum(
            1 for room_id in affected_rooms if db.get(Room, room_id).kind == "laboratory"
        ),
        "affected_transport_riders": affected_riders,
        "affected_hostel_residents": affected_residents,
        "affected_examinations": len(examinations), "affected_services": sorted(affected_services),
        "impact_score": impact_score, "severity": severity, "impact_breakdown": exposure,
        "timeline": timeline, "critical_chain": chain,
        "mitigations": mitigated,
        "assumptions": [
            "Cascades follow the dataset's directed provider-to-dependent edges.",
            "Backup coverage follows the supplied recovery-option capacity descriptions.",
            "Timetable and exam impacts count only activities that overlap the selected outage window.",
            "Impact score is the unweighted mean of the affected-population, faculty, node and room fractions.",
        ],
    }


def resolve_incident(db, incident):
    if incident.resolution_status == "Resolved":
        return False
    entities = json.loads(incident.affected_resources or "{}")
    if not isinstance(entities, dict):
        entities = {}
    node_ids = set(entities.get("nodes", []))
    room_ids = set(entities.get("rooms", []))
    other_open = db.query(Incident).filter(
        Incident.id != incident.id, Incident.resolution_status != "Resolved"
    ).all()
    for other in other_open:
        other_entities = json.loads(other.affected_resources or "{}")
        if not isinstance(other_entities, dict):
            continue
        node_ids.difference_update(other_entities.get("nodes", []))
        room_ids.difference_update(other_entities.get("rooms", []))
    for node_id in node_ids:
        node = db.get(CampusNode, node_id)
        if node:
            node.status = "restored"
    for room_id in room_ids:
        room = db.get(Room, room_id)
        if room:
            room.status = "restored"
    incident.restored_at = datetime.now()
    incident.resolution_status = "Resolved"
    db.commit()
    return True
