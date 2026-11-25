from datetime import datetime
from hashlib import sha1
from itertools import combinations

from app.engines.dependency import AVAILABLE
from app.engines.scheduling import (
    faculty_replacements, room_replacements, transport_replacements, water_recommendation,
)
from app.models.models import (
    Department, Dependency, Event, Examination, Faculty, Resource, Room, TimetableSession,
    TransportRoute,
)

def _hour(value):
    parsed = datetime.strptime(value, "%H:%M")
    return parsed.hour + parsed.minute / 60


def _overlap(a_start, a_duration, b_start, b_duration):
    return a_start < b_start + b_duration and b_start < a_start + a_duration


def _weekday(value):
    return value[:3].title()


def _conflict(
    kind, severity, title, reason, entities, suggestion, recommendations=None,
    auto_fix=None, status="Open",
):
    fingerprint = sha1(f"{kind}|{title}|{reason}".encode()).hexdigest()[:10]
    issue = {
        "id": f"{kind}-{fingerprint}",
        "type": kind, "severity": severity, "title": title, "description": reason,
        "affected_entities": entities, "suggestion": suggestion, "status": status,
    }
    if recommendations is not None:
        issue["recommendations"] = recommendations
    if auto_fix is not None:
        issue["auto_fix"] = auto_fix
    return issue


def _has_verified_backup(db, resource):
    node = resource.node
    if resource.backup_available and node is not None and node.status in AVAILABLE:
        return True
    mitigations = db.query(Dependency).filter(
        Dependency.source_node_id == resource.node_id,
        Dependency.mitigation_resource_id.isnot(None),
    ).all()
    for edge in mitigations:
        backup = db.get(Resource, edge.mitigation_resource_id)
        if (
            backup is not None and backup.backup_available and backup.node is not None
            and backup.node.status in AVAILABLE
        ):
            return True
    return False


def _event_owner(event, departments):
    if not event.organizing_department_id:
        return "organizer not recorded"
    return departments.get(event.organizing_department_id, event.organizing_department_id)


def check_event_booking(
    db, event_name, event_date, start_time, duration_hours, venue_id,
    organizing_department_id=None, excluded_event_id=None,
):
    rooms = {room.id: room for room in db.query(Room).all()}
    sessions = db.query(TimetableSession).filter(TimetableSession.status == "scheduled").all()
    departments = {item.id: item.name for item in db.query(Department).all()}
    source_room = rooms.get(venue_id)
    day = event_date.strftime("%a")
    alternatives = room_replacements(
        db, source_room, source_room.capacity if source_room else 0,
        source_room.kind if source_room else "", day, start_time, duration_hours,
        sessions, event_date=event_date, skip_event_id=excluded_event_id,
    ) if source_room else []
    alternative_ids = [item["id"] for item in alternatives]
    organizer = departments.get(organizing_department_id, organizing_department_id or "organizer not recorded")
    suggestion = (
        f"Move {event_name} to free compatible venue(s) {', '.join(alternative_ids)} or choose a non-overlapping time."
        if alternative_ids else
        f"No free compatible venue was found for {event_name}; choose another time or add a suitable venue."
    )
    issues = []
    if source_room is None or source_room.status not in AVAILABLE:
        reason = "The selected venue is not in the campus room inventory." if source_room is None else (
            f"{venue_id} is currently {source_room.status}."
        )
        issues.append(_conflict(
            "event_venue_unavailable", "HIGH", f"Event venue unavailable: {venue_id}",
            reason, [event_name, venue_id],
            suggestion,
            alternatives,
        ))

    def add_overlap(other_name, other_owner, other_id):
        issues.append(_conflict(
            "event_venue_overlap", "HIGH", f"Venue conflict: {venue_id}",
            f"{event_name} ({organizer}) overlaps {other_name} ({other_owner}) "
            f"at {venue_id} on {event_date} starting {start_time}.",
            [event_name, other_id, venue_id],
            suggestion,
            alternatives,
        ))

    proposed_start = _hour(start_time)
    for event in db.query(Event).all():
        if event.id == excluded_event_id or event.event_date != event_date or event.venue_id != venue_id:
            continue
        if excluded_event_id and event.id <= excluded_event_id:
            continue
        if not _overlap(proposed_start, duration_hours, _hour(event.start_time), event.duration_hours):
            continue
        add_overlap(event.name, _event_owner(event, departments), event.id)

    for exam in db.query(Examination).filter(Examination.status == "scheduled").all():
        if exam.exam_date != event_date or exam.room_id != venue_id:
            continue
        if _overlap(proposed_start, duration_hours, _hour(exam.start_time), exam.duration_hours):
            add_overlap(exam.id, "examination", exam.id)

    for session in sessions:
        if _weekday(session.weekday) != _weekday(day) or session.room_id != venue_id:
            continue
        if _overlap(proposed_start, duration_hours, _hour(session.start_time), session.duration_hours):
            add_overlap(session.id, departments.get(session.department_id, session.department_id), session.id)
    return issues


def detect_conflicts(db):
    rooms = {room.id: room for room in db.query(Room).all()}
    faculty = {person.id: person for person in db.query(Faculty).all()}
    sessions = db.query(TimetableSession).filter(TimetableSession.status == "scheduled").all()
    exams = db.query(Examination).filter(Examination.status == "scheduled").all()
    events = db.query(Event).all()
    departments = {item.id: item.name for item in db.query(Department).all()}
    issues = []

    for session in sessions:
        room = rooms.get(session.room_id)
        person = faculty.get(session.faculty_id)
        start = _hour(session.start_time)
        kind = "lab" if "lab" in session.session_type.lower() or "practical" in session.session_type.lower() else "classroom"
        required_kind = "laboratory" if kind == "lab" else "classroom"
        room_options = room_replacements(
            db, room, session.expected_students, required_kind, session.weekday,
            session.start_time, session.duration_hours, sessions, skip_session_id=session.id,
            department_id=session.department_id,
        )
        room_names = [option["id"] for option in room_options]
        room_suggestion = (
            f"Move {session.id} to compatible free {'lab' if kind == 'lab' else 'classroom'} "
            f"{', '.join(room_names)}."
            if room_names else
            f"No free compatible {'lab' if kind == 'lab' else 'classroom'} fits {session.expected_students} students at {session.start_time}; reschedule or adjust capacity."
        )
        room_fix = (
            {"kind": "room", "session_id": session.id, "room_id": room_options[0]["id"]}
            if room_options else None
        )
        if room:
            if room.capacity < session.expected_students:
                issues.append(_conflict(
                    "capacity", "HIGH", f"Room capacity exceeded: {room.id}",
                    f"{session.id} expects {session.expected_students} students; {room.id} seats {room.capacity}.",
                    [session.id, room.id], room_suggestion, room_options, room_fix,
                ))
            if room.status not in AVAILABLE:
                issues.append(_conflict(
                    "room_status", "HIGH", f"Room unavailable: {room.id}",
                    f"{room.id} is currently {room.status}.", [session.id, room.id],
                    room_suggestion, room_options, room_fix,
                ))
            if kind == "lab" and room.kind != "laboratory":
                issues.append(_conflict(
                    "lab_type", "HIGH", f"Laboratory required: {session.id}",
                    f"{session.session_type} is scheduled in {room.kind} room {room.id}.",
                    [session.id, room.id], room_suggestion, room_options, room_fix,
                ))
        if person:
            expertise = {code.strip().upper() for code in person.expertise_course_codes.replace(",", ";").split(";")}
            if session.course_code.upper() not in expertise:
                replacements = faculty_replacements(db, session, sessions)
                replacement_ids = [item["id"] for item in replacements]
                issues.append(_conflict(
                    "faculty_expertise", "MEDIUM", f"Faculty expertise mismatch: {person.id}",
                    f"{person.id} is not listed as qualified for course {session.course_code}.",
                    [session.id, person.id, session.course_code],
                    f"Assign {session.course_code} to available qualified faculty {', '.join(replacement_ids)}."
                    if replacement_ids else "No available, qualified faculty is free; reschedule or approve a substitute.",
                    replacements,
                    {"kind": "faculty", "session_id": session.id, "faculty_id": replacement_ids[0]}
                    if replacement_ids else None,
                ))
            if person.availability_status.lower() != "available":
                replacements = faculty_replacements(db, session, sessions)
                replacement_ids = [item["id"] for item in replacements]
                issues.append(_conflict(
                    "faculty_availability", "HIGH", f"Faculty unavailable: {person.id}",
                    f"{person.id} is marked {person.availability_status}.", [session.id, person.id],
                    f"Reassign {session.id} to available qualified faculty {', '.join(replacement_ids)}."
                    if replacement_ids else "No available, qualified faculty is free; reschedule or approve a substitute.",
                    replacements,
                    {"kind": "faculty", "session_id": session.id, "faculty_id": replacement_ids[0]}
                    if replacement_ids else None,
                ))
        if session.duration_hours <= 0 or start + session.duration_hours > 24:
            issues.append(_conflict(
                "time_window", "HIGH", f"Invalid session time: {session.id}",
                "The session duration falls outside a valid day schedule.", [session.id],
                "Correct the start time or duration.",
            ))

    for left, right in combinations(sessions, 2):
        if left.weekday != right.weekday:
            continue
        left_start, right_start = _hour(left.start_time), _hour(right.start_time)
        if not _overlap(left_start, left.duration_hours, right_start, right.duration_hours):
            continue
        entities = [left.id, right.id]
        if left.room_id == right.room_id:
            activity = right
            source_room = rooms.get(activity.room_id)
            kind = "laboratory" if "lab" in activity.session_type.lower() or "practical" in activity.session_type.lower() else "classroom"
            replacements = room_replacements(
                db, source_room, activity.expected_students, kind, activity.weekday,
                activity.start_time, activity.duration_hours, sessions,
                skip_session_id=activity.id, department_id=activity.department_id,
            )
            replacement_ids = [item["id"] for item in replacements]
            issues.append(_conflict(
                "room_overlap", "HIGH", f"Room booking overlap: {left.room_id}",
                f"{left.id} and {right.id} overlap on {left.weekday}.", entities + [left.room_id],
                f"Move {right.id} to free compatible room(s) {', '.join(replacement_ids)}."
                if replacement_ids else "No compatible room is free; reschedule one booking.",
                replacements,
                {"kind": "room", "session_id": right.id, "room_id": replacement_ids[0]}
                if replacement_ids else None,
            ))
        if left.faculty_id == right.faculty_id:
            replacements = faculty_replacements(db, right, sessions)
            replacement_ids = [item["id"] for item in replacements]
            issues.append(_conflict(
                "faculty_overlap", "HIGH", f"Faculty scheduling overlap: {left.faculty_id}",
                f"{left.id} and {right.id} require the same faculty at the same time.",
                entities + [left.faculty_id],
                f"Reassign {right.id} to available qualified faculty {', '.join(replacement_ids)}."
                if replacement_ids else "No qualified faculty is free at this time; reschedule one session.",
                replacements,
                {"kind": "faculty", "session_id": right.id, "faculty_id": replacement_ids[0]}
                if replacement_ids else None,
            ))
        if left.cohort_id == right.cohort_id:
            issues.append(_conflict(
                "cohort_overlap", "HIGH", f"Student cohort overlap: {left.cohort_id}",
                f"{left.id} and {right.id} schedule the same cohort concurrently.",
                entities + [left.cohort_id], "Reschedule one activity for the cohort.",
            ))

    for exam in exams:
        room = rooms.get(exam.room_id)
        start = _hour(exam.start_time)
        weekday = exam.exam_date.strftime("%a")
        exam_room_options = room_replacements(
            db, room, exam.student_count, "exam_hall", weekday, exam.start_time,
            exam.duration_hours, sessions, event_date=exam.exam_date,
        )
        exam_room_ids = [item["id"] for item in exam_room_options]
        exam_room_suggestion = (
            f"Move {exam.id} to examination hall(s) {', '.join(exam_room_ids)}."
            if exam_room_ids else
            f"No free examination hall fits {exam.student_count} candidates; split the cohort or reschedule."
        )
        exam_room_fix = (
            {"kind": "room", "exam_id": exam.id, "room_id": exam_room_ids[0]}
            if exam_room_ids else None
        )
        if room and exam.student_count > room.capacity:
            issues.append(_conflict(
                "exam_capacity", "CRITICAL", f"Examination hall capacity exceeded: {room.id}",
                f"{exam.id} seats {exam.student_count} candidates; {room.id} capacity is {room.capacity}.",
                [exam.id, room.id], exam_room_suggestion, exam_room_options, exam_room_fix,
            ))
        if room and room.kind != "exam_hall" and exam.exam_mode.lower() != "online":
            issues.append(_conflict(
                "exam_room_type", "HIGH", f"Invalid examination venue: {room.id}",
                f"{exam.id} is an offline examination assigned to {room.kind}.",
                [exam.id, room.id], exam_room_suggestion, exam_room_options, exam_room_fix,
            ))
        for session in sessions:
            session_day = session.weekday[:3].title()
            if session_day != weekday:
                continue
            if not _overlap(start, exam.duration_hours, _hour(session.start_time), session.duration_hours):
                continue
            if session.room_id == exam.room_id:
                issues.append(_conflict(
                    "exam_room_overlap", "CRITICAL", f"Examination room double-booked: {room.id if room else exam.room_id}",
                    f"{exam.id} overlaps scheduled session {session.id}.", [exam.id, session.id, exam.room_id],
                    exam_room_suggestion, exam_room_options, exam_room_fix,
                ))
            if exam.invigilator_id == session.faculty_id:
                issues.append(_conflict(
                    "invigilator_overlap", "HIGH", f"Invigilator is already teaching: {exam.invigilator_id}",
                    f"{exam.id} conflicts with {session.id} for the assigned invigilator.",
                    [exam.id, session.id, exam.invigilator_id], "Assign a free, qualified invigilator.",
                ))
        for other in exams:
            if other.id <= exam.id or other.exam_date != exam.exam_date:
                continue
            if not _overlap(start, exam.duration_hours, _hour(other.start_time), other.duration_hours):
                continue
            if exam.room_id == other.room_id:
                issues.append(_conflict(
                    "exam_room_overlap", "CRITICAL", f"Examination hall double-booked: {exam.room_id}",
                    f"{exam.id} and {other.id} overlap on {exam.exam_date}.",
                    [exam.id, other.id, exam.room_id], exam_room_suggestion, exam_room_options, exam_room_fix,
                ))
            if exam.invigilator_id == other.invigilator_id:
                issues.append(_conflict(
                    "invigilator_overlap", "CRITICAL", f"Invigilator assigned twice: {exam.invigilator_id}",
                    f"{exam.id} and {other.id} overlap for one invigilator.",
                    [exam.id, other.id, exam.invigilator_id], "Assign a different available invigilator.",
                ))
            if exam.cohort_id == other.cohort_id:
                issues.append(_conflict(
                    "cohort_exam_overlap", "CRITICAL", f"Cohort has simultaneous exams: {exam.cohort_id}",
                    f"{exam.id} and {other.id} overlap for the same cohort.",
                    [exam.id, other.id, exam.cohort_id], "Reschedule one examination.",
                ))

    for event in events:
        issues.extend(check_event_booking(
            db, event.name, event.event_date, event.start_time, event.duration_hours,
            event.venue_id, event.organizing_department_id, excluded_event_id=event.id,
        ))

    for route in db.query(TransportRoute).all():
        if route.assigned_students < route.daily_capacity:
            continue
        alternatives = transport_replacements(db, route, route.assigned_students)
        usable = [item for item in alternatives if item["can_fit"]]
        usable_routes = ", ".join(
            "{} ({} seats)".format(item["bus_id"], item["spare_seats"]) for item in usable
        )
        suggestion = (
            f"Move {route.assigned_students} riders to spare capacity on "
            f"{usable_routes}."
            if usable else
            f"No single alternate route has {route.assigned_students} verified spare seats; split riders only after checking combined capacity."
        )
        issues.append(_conflict(
            "transport_capacity", "HIGH", f"Route at capacity: {route.route_name}",
            f"{route.bus_id} has {route.assigned_students} riders for {route.daily_capacity} seats.",
            [route.id, route.bus_id], suggestion, alternatives,
        ))

    for resource in db.query(Resource).all():
        node = resource.node
        if node is None:
            continue
        if resource.resource_type.lower() == "water" and node.status not in AVAILABLE:
            issues.append(_conflict(
                "hostel_water_outage", "HIGH", f"Water service unavailable: {node.name}",
                f"The water resource in zone {resource.zone_id} is currently {node.status}.",
                [node.id, resource.zone_id], water_recommendation(db, resource),
            ))
        if _has_verified_backup(db, resource):
            continue
        criticality = node.criticality_label.lower()
        if criticality not in ("critical", "high"):
            continue
        issues.append(_conflict(
            "resource_backup_gap",
            "CRITICAL" if criticality == "critical" else "HIGH",
            f"Backup not recorded: {node.name}",
            f"{node.name} is classified as {criticality} priority, but no available backup is "
            f"recorded for zone {resource.zone_id}.",
            [node.id, resource.zone_id],
            "Record a tested standby resource or document an approved exception.",
            status="Needs review",
        ))

    unique = {}
    for issue in issues:
        unique[(issue["type"], issue["title"], tuple(issue["affected_entities"]))] = issue
    return sorted(unique.values(), key=lambda issue: ({"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}.get(issue["severity"], 4), issue["title"]))
