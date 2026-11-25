import networkx as nx

from app.engines.dependency import AVAILABLE, build_graph
from app.models.models import (
    CampusNode, Department, Dependency, Faculty, Hostel, Incident, Resource,
    Room, Student, TimetableSession, TransportRoute,
)

WEEKLY_ROOM_HOURS = 40


def _available(status):
    return status in AVAILABLE


def dashboard_data(db):
    departments = db.query(Department).all()
    students = db.query(Student).filter(Student.status == "active").count()
    faculty = db.query(Faculty).count()
    rooms = db.query(Room).all()
    sessions = db.query(TimetableSession).filter(TimetableSession.status == "scheduled").all()
    room_scheduled_hours = {}
    for session in sessions:
        room_scheduled_hours[session.room_id] = (
            room_scheduled_hours.get(session.room_id, 0) + session.duration_hours
        )
    nodes = db.query(CampusNode).all()
    incidents = db.query(Incident).order_by(Incident.timestamp.desc()).limit(6).all()
    active_incidents = db.query(Incident).filter(Incident.resolution_status != "Resolved").count()
    dept_status = []
    for department in departments:
        dept_rooms = [room for room in rooms if room.department_id == department.id]
        available_rooms = sum(_available(room.status) for room in dept_rooms)
        weekly_capacity_hours = len(dept_rooms) * WEEKLY_ROOM_HOURS
        free_room_hours = sum(
            max(WEEKLY_ROOM_HOURS - room_scheduled_hours.get(room.id, 0), 0)
            for room in dept_rooms if _available(room.status)
        )
        health = round(100 * available_rooms / len(dept_rooms)) if dept_rooms else 100
        dept_status.append({
            "name": department.id,
            "value": health,
            "capacity_percent": round(100 * free_room_hours / weekly_capacity_hours, 1)
            if weekly_capacity_hours else 100,
            "available_rooms": available_rooms,
            "total_rooms": len(dept_rooms),
            "scheduled_hours": round(sum(
                room_scheduled_hours.get(room.id, 0) for room in dept_rooms
            ), 1),
            "students": db.query(Student).filter(
                Student.department_id == department.id, Student.status == "active"
            ).count(),
            "faculty": db.query(Faculty).filter(Faculty.department_id == department.id).count(),
        })

    def availability(name, records, state):
        return {
            "name": name,
            "value": round(100 * sum(state(item) for item in records) / len(records)) if records else 100,
            "total": len(records),
        }

    def backup_coverage(name, records):
        return {
            "name": name,
            "value": round(100 * sum(item.backup_available for item in records) / len(records))
            if records else 0,
            "total": len(records),
        }

    power = db.query(Resource).filter(Resource.resource_type.in_(["electricity", "backup_power"])).all()
    internet = db.query(Resource).filter(Resource.resource_type == "internet").all()
    labs = [room for room in rooms if room.kind == "laboratory"]
    transport = db.query(TransportRoute).all()
    transport_total = sum(route.daily_capacity for route in transport)
    transport_free = sum(max(route.daily_capacity - route.assigned_students, 0) for route in transport)
    resource_status = [
        backup_coverage("Power backup coverage", power),
        backup_coverage("Internet backup coverage", internet),
        availability("Rooms available", rooms, lambda item: _available(item.status)),
        availability("Labs available", labs, lambda item: _available(item.status)),
        {
            "name": "Transport spare seats",
            "value": round(100 * transport_free / transport_total) if transport_total else 100,
            "total": transport_total,
        },
    ]
    return {
        "stats": {
            "departments": len(departments), "students": students, "faculty": faculty,
            "rooms": len(rooms), "laboratories": len(labs), "active_incidents": active_incidents,
            "critical_alerts": sum(node.status in ("failed", "degraded", "under_maintenance") for node in nodes),
            "health": round(100 * sum(_available(node.status) for node in nodes) / len(nodes)) if nodes else 100,
        },
        "department_status": dept_status,
        "resource_status": resource_status,
        "activity": [
            {"time": incident.timestamp.strftime("%d %b %H:%M"),
             "title": (
                 f"Failure simulation at {incident.failed_node.name}"
                 if incident.failed_node and "simulat" in incident.failure_type.lower()
                 else f"{incident.failure_type}: {incident.failed_node.name}"
                 if incident.failed_node
                 else f"{incident.failure_type}: {incident.failed_resource}"
             ),
             "status": "Resolved" if incident.resolution_status == "Resolved" else "Needs attention",
             "kind": "success" if incident.resolution_status == "Resolved" else "warning"}
            for incident in incidents
        ],
    }


def resource_optimization(db):
    rooms = db.query(Room).all()
    sessions = db.query(TimetableSession).filter(TimetableSession.status == "scheduled").all()
    faculty = db.query(Faculty).all()
    routes = db.query(TransportRoute).all()
    resources = db.query(Resource).all()
    hostels = db.query(Hostel).all()
    room_usage = {}
    for room in rooms:
        used = sum(session.duration_hours for session in sessions if session.room_id == room.id)
        room_usage[room.id] = {
            "id": room.id, "type": room.kind, "building": room.building,
            "capacity": room.capacity, "scheduled_hours": round(used, 1),
            "weekly_available_hours": WEEKLY_ROOM_HOURS,
            "utilization_percent": round(min(100, used / WEEKLY_ROOM_HOURS * 100), 1),
            "status": room.status,
        }
    faculty_usage = []
    for person in faculty:
        used = sum(session.duration_hours for session in sessions if session.faculty_id == person.id)
        faculty_usage.append({
            "id": person.id, "department_id": person.department_id,
            "scheduled_hours": round(used, 1), "max_weekly_hours": person.max_weekly_hours,
            "utilization_percent": round(min(100, used / max(person.max_weekly_hours, 1) * 100), 1),
            "availability": person.availability_status,
        })
    return {
        "rooms": list(room_usage.values()),
        "laboratories": [item for item in room_usage.values() if item["type"] == "laboratory"],
        "faculty": faculty_usage,
        "transport": [{
            "id": route.id, "bus_id": route.bus_id, "route": route.route_name,
            "capacity": route.daily_capacity, "assigned": route.assigned_students,
            "spare_seats": max(route.daily_capacity - route.assigned_students, 0),
            "overloaded": route.assigned_students > route.daily_capacity,
        } for route in routes],
        "backup_power": [{
            "id": resource.node_id, "status": resource.node.status,
            "backup_available": resource.backup_available, "zone": resource.zone_id,
            "capacity_note": "Quantitative capacity not supplied in dataset",
        } for resource in resources if resource.resource_type == "backup_power"],
        "water_storage": [{
            "id": hostel.id, "occupied": hostel.occupied, "capacity": hostel.capacity,
            "backup_hours": hostel.backup_hours,
        } for hostel in hostels],
        "internet": [{
            "id": resource.node_id, "status": resource.node.status,
            "backup_available": resource.backup_available, "zone": resource.zone_id,
        } for resource in resources if resource.resource_type == "internet"],
        "assumptions": ["Room availability is calculated on the supplied 40-hour Monday-Friday schedule.",
                        "Unprovided power and internet demand/capacity is reported as unknown, not estimated."],
    }


def risk_data(db):
    graph, resources = build_graph(db)
    incidents = db.query(Incident).all()
    incident_count = {}
    for incident in incidents:
        if incident.failed_node_id:
            incident_count[incident.failed_node_id] = incident_count.get(incident.failed_node_id, 0) + 1
    records = []
    for node_id, attrs in graph.nodes(data=True):
        dependents = nx.descendants(graph, node_id)
        outgoing = list(graph.out_edges(node_id, data=True))
        mitigation_complete = bool(outgoing) and all(
            edge.get("mitigation_resource_id")
            and resources.get(edge["mitigation_resource_id"])
            and resources[edge["mitigation_resource_id"]].backup_available
            and resources[edge["mitigation_resource_id"]].node.status in AVAILABLE
            for _, _, edge in outgoing
        )
        history = incident_count.get(node_id, 0)
        components = {
            "criticality": round(attrs["criticality"] * 100),
            "dependency_reach": round(100 * len(dependents) / max(len(graph.nodes) - 1, 1)),
            "incident_history": min(history * 20, 100),
            "backup_gap": 0 if mitigation_complete else 100 if outgoing else 0,
        }
        risk_index = max(components.values())
        records.append({
            "id": node_id, "name": attrs["name"], "type": attrs["type"],
            "status": attrs["status"], "criticality": attrs["criticality_label"],
            "direct_dependents": len(outgoing), "downstream_nodes": len(dependents),
            "incident_history_count": history, "single_point_of_failure": bool(outgoing) and not mitigation_complete,
            "backup_coverage": mitigation_complete, "risk_index": risk_index,
            "risk_components": components,
        })
    records.sort(key=lambda row: (-row["risk_index"], row["name"]))
    return {
        "resources": records,
        "single_points_of_failure": [row for row in records if row["single_point_of_failure"]],
        "methodology": "Explainable index = maximum of criticality, normalized downstream reach, incident-history indicator (20 points per recorded incident, capped), and unmitigated-outgoing-dependency indicator. It is not a failure probability.",
    }
