from app.engines.dependency import AVAILABLE
from app.models.models import Event, Examination, Faculty, Hostel, Resource, Room, TimetableSession, TransportRoute


GENERIC_EQUIPMENT = {"pc", "projector", "ups", "whiteboard", "wifi", "cctv", "desks"}


def _hour(value):
    hours, minutes = value.split(":")
    return int(hours) + int(minutes) / 60


def _overlap(left, left_duration, right, right_duration):
    return left < right + right_duration and right < left + left_duration


def _weekday(value):
    return value[:3].title()


def _equipment_keys(value):
    return {entry.split(":", 1)[0].strip().lower() for entry in value.split(";") if entry.strip()}


def faculty_replacements(db, session, sessions, limit=3):
    course = session.course_code.strip().upper()
    exams = db.query(Examination).filter(Examination.status == "scheduled").all()
    candidates = []
    for person in db.query(Faculty).all():
        if person.id == session.faculty_id or person.availability_status.lower() != "available":
            continue
        expertise = {
            code.strip().upper()
            for code in person.expertise_course_codes.replace(",", ";").split(";")
            if code.strip()
        }
        if course not in expertise:
            continue
        assigned = [item for item in sessions if item.faculty_id == person.id and item.id != session.id]
        weekly_hours = sum(item.duration_hours for item in assigned)
        if weekly_hours + session.duration_hours > person.max_weekly_hours:
            continue
        if any(
            _weekday(item.weekday) == _weekday(session.weekday)
            and _overlap(
                _hour(session.start_time), session.duration_hours,
                _hour(item.start_time), item.duration_hours,
            )
            for item in assigned
        ):
            continue
        if any(
            exam.invigilator_id == person.id
            and _weekday(exam.exam_date.strftime("%a")) == _weekday(session.weekday)
            and _overlap(
                _hour(session.start_time), session.duration_hours,
                _hour(exam.start_time), exam.duration_hours,
            )
            for exam in exams
        ):
            continue
        candidates.append({
            "id": person.id,
            "department_id": person.department_id,
            "weekly_hours": round(weekly_hours, 1),
        })
    candidates.sort(key=lambda item: (
        item["department_id"] != session.department_id, item["weekly_hours"], item["id"],
    ))
    return candidates[:limit]


def _room_is_free(db, room_id, day, start_time, duration, sessions, skip_session_id=None,
                  event_date=None, skip_event_id=None):
    start = _hour(start_time)
    if any(
        session.id != skip_session_id and session.room_id == room_id
        and _weekday(session.weekday) == _weekday(day)
        and _overlap(start, duration, _hour(session.start_time), session.duration_hours)
        for session in sessions
    ):
        return False
    exams = db.query(Examination).filter(Examination.status == "scheduled").all()
    if any(
        exam.room_id == room_id
        and (exam.exam_date == event_date if event_date else _weekday(exam.exam_date.strftime("%a")) == _weekday(day))
        and _overlap(start, duration, _hour(exam.start_time), exam.duration_hours)
        for exam in exams
    ):
        return False
    events = db.query(Event).all()
    return not any(
        event.id != skip_event_id and event.venue_id == room_id
        and (event.event_date == event_date if event_date else _weekday(event.event_date.strftime("%a")) == _weekday(day))
        and _overlap(start, duration, _hour(event.start_time), event.duration_hours)
        for event in events
    )


def room_replacements(db, current_room, capacity, required_kind, day, start_time, duration,
                     sessions, skip_session_id=None, event_date=None, skip_event_id=None,
                     department_id=None, limit=3):
    if current_room is None:
        return []
    required_equipment = _equipment_keys(current_room.equipment) - GENERIC_EQUIPMENT
    if required_kind == "laboratory":
        required_equipment.update(_equipment_keys(current_room.equipment) - GENERIC_EQUIPMENT)
    candidates = []
    for room in db.query(Room).filter(Room.status.in_(tuple(AVAILABLE))).all():
        if room.id == current_room.id or room.capacity < capacity:
            continue
        if room.kind != required_kind:
            continue
        if (
            required_kind == "laboratory" and current_room.kind == "laboratory"
            and room.lab_type != current_room.lab_type
        ):
            continue
        if not required_equipment.issubset(_equipment_keys(room.equipment)):
            continue
        if not _room_is_free(
            db, room.id, day, start_time, duration, sessions,
            skip_session_id=skip_session_id, event_date=event_date,
            skip_event_id=skip_event_id,
        ):
            continue
        candidates.append({
            "id": room.id,
            "building": room.building,
            "capacity": room.capacity,
            "kind": room.kind,
            "department_id": room.department_id,
        })
    candidates.sort(key=lambda item: (
        item["department_id"] != department_id, item["capacity"] - capacity, item["id"],
    ))
    return candidates[:limit]


def transport_replacements(db, route, required_seats=1, limit=3):
    candidates = []
    for candidate in db.query(TransportRoute).all():
        if candidate.id == route.id:
            continue
        spare = max(candidate.daily_capacity - candidate.assigned_students, 0)
        if spare:
            candidates.append({
                "bus_id": candidate.bus_id,
                "route": candidate.route_name,
                "spare_seats": spare,
                "can_fit": spare >= required_seats,
            })
    candidates.sort(key=lambda item: (not item["can_fit"], -item["spare_seats"], item["bus_id"]))
    return candidates[:limit]


def water_recommendation(db, resource):
    hostels = db.query(Hostel).filter(Hostel.water_zone == resource.zone_id).order_by(Hostel.id).all()
    tanks = [
        item for item in db.query(Resource).filter(Resource.resource_type == "water").all()
        if item.node is not None and "tank" in item.node.name.lower()
        and item.zone_id == resource.zone_id
        and item.node.status in AVAILABLE and item.backup_available
    ]
    if not hostels or not tanks:
        return "Arrange an alternate water supply and inspect the hostel reserve; no verified tank capacity is recorded."
    reserve_details = ", ".join(f"{hostel.id}: {hostel.backup_hours:g}h" for hostel in hostels)
    minimum_reserve = min(hostel.backup_hours for hostel in hostels)
    tank_names = ", ".join(item.node.name for item in tanks)
    return (
        f"Use {tank_names} and monitor hostel reserves ({reserve_details}); "
        f"the shortest recorded buffer is {minimum_reserve:g} hours. "
        "Arrange an alternate supply if the outage may exceed that buffer."
    )
