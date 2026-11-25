import json
from datetime import datetime

from app.engines.dependency import AVAILABLE
from app.models.models import (
    CampusNode, Dependency, Event, Examination, Faculty, Incident, RecoveryOption,
    Hostel, Resource, Room, Student, TimetableSession, TransportRoute,
)


DISRUPTION_ORDER = {"low": 0, "medium": 1, "high": 2}


def _equipment_keys(value):
    return {entry.split(":", 1)[0].strip().lower() for entry in value.split(";") if entry.strip()}


def _family(db, roots):
    families = set()
    for root in roots:
        node = db.get(CampusNode, root)
        resource = db.get(Resource, root)
        name = f"{root} {node.name if node else ''} {resource.resource_type if resource else ''}".lower()
        if "power" in name or "electric" in name or "grid" in name:
            families.add("power")
        elif "internet" in name or "isp" in name or "network" in name:
            families.add("internet")
        elif "water" in name:
            families.add("water")
        elif "bus" in name or "transport" in name:
            families.add("transport")
        elif "lab" in name:
            families.add("lab")
    return families


def _room_free(db, room_id, activity, incident):
    start = datetime.fromisoformat(incident.timestamp.isoformat())
    weekday = start.strftime("%a")
    start_hour = int(activity.start_time[:2]) + int(activity.start_time[3:5]) / 60
    duration = activity.duration_hours
    if isinstance(activity, TimetableSession):
        return not any(
            other.id != activity.id and other.room_id == room_id
            and other.weekday[:3].title() == activity.weekday[:3].title()
            and _overlap(start_hour, duration, _hour(other.start_time), other.duration_hours)
            for other in db.query(TimetableSession).all()
        )
    date = activity.exam_date if isinstance(activity, Examination) else activity.event_date
    if date != start.date():
        return True
    for exam in db.query(Examination).filter(Examination.exam_date == date).all():
        if exam.id != activity.id and exam.room_id == room_id and _overlap(
            start_hour, duration, _hour(exam.start_time), exam.duration_hours
        ):
            return False
    for session in db.query(TimetableSession).filter(TimetableSession.weekday == weekday).all():
        if session.room_id == room_id and _overlap(
            start_hour, duration, _hour(session.start_time), session.duration_hours
        ):
            return False
    for event in db.query(Event).filter(Event.event_date == date).all():
        if event.id != activity.id and event.venue_id == room_id and _overlap(
            start_hour, duration, _hour(event.start_time), event.duration_hours
        ):
            return False
    return True


def _hour(value):
    hours, minutes = value.split(":")
    return int(hours) + int(minutes) / 60


def _overlap(left, left_duration, right, right_duration):
    return left < right + right_duration and right < left + left_duration


def _relocate_activities(db, incident, entities, option):
    session_ids = set(entities.get("sessions", []))
    exam_ids = set(entities.get("examinations", []))
    activities = [
        item for item in db.query(TimetableSession).filter(TimetableSession.id.in_(session_ids)).all()
    ] + [
        item for item in db.query(Examination).filter(Examination.id.in_(exam_ids)).all()
    ]
    required_room = option.required_room_id
    target_id = option.required_resource_id
    reserved = []
    allocations = []
    constraints = []
    for activity in activities:
        source = db.get(Room, activity.room_id)
        if source is None:
            constraints.append(f"Original venue {activity.room_id} is missing.")
            continue
        is_exam = isinstance(activity, Examination)
        needed_kind = "exam_hall" if is_exam else (
            "laboratory" if source.kind == "laboratory" else source.kind
        )
        needed_capacity = activity.student_count if is_exam else activity.expected_students
        specialized = _equipment_keys(source.equipment) - {"pc", "projector", "ups", "whiteboard", "wifi", "cctv", "desks"}
        candidates = db.query(Room).filter(
            Room.kind == needed_kind,
            Room.capacity >= needed_capacity,
            Room.status.in_(("operational", "restored")),
        ).all()
        if required_room:
            candidates = [room for room in candidates if room.id == required_room]
        elif target_id in {room.id for room in candidates}:
            candidates = [room for room in candidates if room.id == target_id]
        picked = None
        for candidate in sorted(candidates, key=lambda room: (room.capacity - needed_capacity, room.id)):
            keys = _equipment_keys(candidate.equipment)
            if not specialized.issubset(keys):
                continue
            if not _room_free(db, candidate.id, activity, incident):
                continue
            if any(
                previous_room == candidate.id and previous_start == activity.start_time
                and previous_day == (
                    activity.weekday if isinstance(activity, TimetableSession) else activity.exam_date.isoformat()
                )
                for previous_room, previous_day, previous_start, _duration in reserved
            ):
                continue
            picked = candidate
            break
        if picked is None:
            constraints.append(
                f"No free {needed_kind} with capacity {needed_capacity} and required equipment "
                f"for {activity.id} at {activity.start_time}."
            )
            continue
        day = activity.weekday if isinstance(activity, TimetableSession) else activity.exam_date.isoformat()
        reserved.append((picked.id, day, activity.start_time, activity.duration_hours))
        allocations.append({"activity_id": activity.id, "from_room": source.id, "to_room": picked.id})
    return allocations, constraints


def recovery_data(db, incident_id):
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise ValueError("Incident not found.")
    try:
        entities = json.loads(incident.affected_resources or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError("Incident impact record is invalid.") from exc
    if not isinstance(entities, dict):
        entities = {}
    roots = [node_id.strip() for node_id in incident.failed_resource.split(",") if node_id.strip()]
    families = _family(db, roots)
    options = db.query(RecoveryOption).filter(
        RecoveryOption.scenario_family.in_(families)
    ).all() if families else []
    plans = []
    for option in options:
        constraints = []
        allocations = []
        affected_nodes = set(entities.get("nodes", []))
        affected_students = 0
        feasible = True
        restored_nodes = []
        resource = db.get(Resource, option.required_resource_id)
        node = db.get(CampusNode, option.required_resource_id)
        room = db.get(Room, option.required_resource_id)
        if option.scenario_family == "transport":
            target_route = db.query(TransportRoute).filter(
                TransportRoute.bus_id == option.required_resource_id
            ).first()
            failed_route = db.query(TransportRoute).filter(
                TransportRoute.bus_id.in_(roots)
            ).first()
            if target_route is None or failed_route is None:
                feasible = False
                constraints.append("Dataset does not link the failed bus and replacement route.")
            else:
                spare = max(target_route.daily_capacity - target_route.assigned_students, 0)
                required = failed_route.assigned_students
                if target_route.bus_id in roots or spare < required:
                    feasible = False
                    constraints.append(f"Replacement route has {spare} spare seats for {required} riders.")
                else:
                    restored_nodes = [target_route.id]
        elif resource and node:
            if node.status not in AVAILABLE or not resource.backup_available:
                feasible = False
                constraints.append(f"Required backup {node.name} is not available.")
            elif option.scenario_family == "power" and "priority_loads_only" in option.capacity_limit:
                dependents = [
                    edge.target_node_id for edge in db.query(Dependency).filter(
                        Dependency.source_node_id.in_(roots),
                        Dependency.mitigation_resource_id == option.required_resource_id,
                    ).all()
                ]
                non_priority = [
                    node_id for node_id in dependents
                    if (db.get(CampusNode, node_id).criticality if db.get(CampusNode, node_id) else 0) < 0.8
                ]
                restored_nodes = [item for item in dependents if item not in non_priority]
                if non_priority:
                    feasible = False
                    constraints.append(
                        "The dataset limits generator use to priority loads; "
                        + f"{len(non_priority)} dependent service(s) do not meet that criticality."
                    )
            elif option.scenario_family == "internet":
                constraints.append(
                    "Backup link is limited to 60% traffic, but the dataset contains no per-service bandwidth demand."
                )
                feasible = False
            elif option.scenario_family == "water":
                source_resource = next(
                    (db.get(Resource, root) for root in roots if db.get(Resource, root)
                     and db.get(Resource, root).resource_type == "water"),
                    None,
                )
                hostels = db.query(Hostel).filter(
                    Hostel.water_zone == source_resource.zone_id
                ).all() if source_resource else db.query(Hostel).all()
                backup_hours = min((item.backup_hours for item in hostels), default=0)
                required_hours = incident.duration_minutes / 60
                if required_hours > backup_hours:
                    feasible = False
                    constraints.append(
                        f"Water buffer covers {backup_hours:g} hours; outage duration is {required_hours:g} hours."
                    )
                else:
                    restored_nodes = list(affected_nodes)
        elif room:
            allocations, constraints = _relocate_activities(db, incident, entities, option)
            feasible = not constraints
            restored_nodes = list(entities.get("sessions", [])) + list(entities.get("examinations", []))
            cohorts = entities.get("cohorts", [])
            affected_students = db.query(Student).filter(
                Student.cohort_id.in_(cohorts), Student.status == "active"
            ).count() if cohorts else 0
        else:
            feasible = False
            constraints.append("Required replacement resource is not represented as a compatible room or campus node.")

        plans.append({
            "id": option.id, "name": option.action, "scenario_family": option.scenario_family,
            "feasible": feasible, "services_restored": restored_nodes,
            "students_restored": affected_students, "estimated_setup_minutes": option.estimated_setup_minutes,
            "cost_units": option.direct_cost_units, "disruption": option.disruption_level,
            "allocations": allocations, "constraints": constraints,
            "capacity_limit": option.capacity_limit,
        })

    plans.sort(key=lambda plan: (
        not plan["feasible"], -len(plan["services_restored"]),
        -plan["students_restored"], plan["estimated_setup_minutes"],
        plan["cost_units"], DISRUPTION_ORDER.get(plan["disruption"].lower(), 9),
    ))
    recommended = next((plan for plan in plans if plan["feasible"]), None)
    reason = (
        "Recommended as the feasible option restoring the most listed services/activities, "
        "then minimizing setup time, cost and disruption in that order."
        if recommended else "No feasible recovery option satisfies the supplied capacity and availability constraints."
    )
    return {
        "incident_id": incident.id, "scenario_families": sorted(families),
        "plans": plans, "recommended_plan_id": recommended["id"] if recommended else None,
        "recommendation_reason": reason,
        "optimization_method": "Constraint-filtered plans ranked lexicographically by feasibility, restored service/activity count, affected students, setup time, cost and disruption; no synthetic score is assigned.",
        "data_limitations": [
            "Bandwidth demand per service and quantitative generator loads are absent from the source dataset.",
            "Room equipment compatibility uses the source room's specialized equipment keys; timetable records do not specify per-course equipment requirements.",
        ],
    }
