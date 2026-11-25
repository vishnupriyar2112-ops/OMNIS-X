import unittest
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.engines.conflicts import check_event_booking, detect_conflicts
from app.engines.scheduling import faculty_replacements, transport_replacements, water_recommendation
from app.models.models import (
    CampusNode, Dependency, Department, Event, Faculty, Hostel, Resource, Room,
    TimetableAssignmentOverride, TimetableSession, TransportRoute,
    TransportRouteAssignmentOverride,
)
from database import Base
from seed import _apply_operational_overrides


class SchedulingRecommendationTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        self.addCleanup(engine.dispose)
        self.addCleanup(self.db.close)
        self.department = Department(id="CSE", name="Computer Science")
        self.db.add(self.department)

    def test_event_check_flags_overlapping_venue_and_suggests_free_alternative(self):
        venue = Room(id="AUD-1", building="Main", kind="auditorium", capacity=100)
        alternative = Room(id="AUD-2", building="Main", kind="auditorium", capacity=120)
        event = Event(
            id="EV-1", name="Tech Day", event_type="Festival",
            organizing_department_id="CSE", event_date=date(2026, 3, 16),
            start_time="09:00", duration_hours=2, venue_id=venue.id, priority="high",
        )
        self.db.add_all([venue, alternative, event])
        self.db.commit()

        conflicts = check_event_booking(
            self.db, "Project Expo", date(2026, 3, 16), "10:00", 1,
            venue.id, "CSE",
        )

        overlap = next(item for item in conflicts if item["type"] == "event_venue_overlap")
        self.assertIn("Tech Day", overlap["description"])
        self.assertEqual([item["id"] for item in overlap["recommendations"]], [alternative.id])

    def test_event_check_allows_non_overlapping_same_day_booking(self):
        venue = Room(id="AUD-1", building="Main", kind="auditorium", capacity=100)
        event = Event(
            id="EV-1", name="Tech Day", event_type="Festival",
            event_date=date(2026, 3, 16), start_time="09:00",
            duration_hours=2, venue_id=venue.id, priority="high",
        )
        self.db.add_all([venue, event])
        self.db.commit()

        conflicts = check_event_booking(
            self.db, "Project Expo", date(2026, 3, 16), "11:00", 1, venue.id,
        )

        self.assertFalse(any(item["type"] == "event_venue_overlap" for item in conflicts))

    def test_faculty_replacement_must_be_available_and_course_qualified(self):
        room = Room(id="R-1", building="Main", kind="classroom", capacity=40)
        unavailable = Faculty(
            id="F-1", department_id="CSE", designation="Lecturer",
            expertise_course_codes="CS101", availability_status="unavailable",
        )
        qualified = Faculty(
            id="F-2", department_id="CSE", designation="Lecturer",
            expertise_course_codes="CS101", availability_status="available",
        )
        session = TimetableSession(
            id="S-1", cohort_id="CSE-1", department_id="CSE", course_code="CS101",
            session_type="lecture", room_id=room.id, faculty_id=unavailable.id,
            weekday="Mon", start_time="09:00", duration_hours=1, expected_students=30,
            status="scheduled",
        )
        self.db.add_all([room, unavailable, qualified, session])
        self.db.commit()

        replacements = faculty_replacements(self.db, session, [session])

        self.assertEqual([item["id"] for item in replacements], [qualified.id])

    def test_transport_alternatives_report_whether_all_riders_fit(self):
        full = TransportRoute(
            id="R-1", bus_id="BUS-1", route_name="North", daily_capacity=40,
            assigned_students=40, arrival_buffer_minutes=10,
        )
        spare = TransportRoute(
            id="R-2", bus_id="BUS-2", route_name="South", daily_capacity=80,
            assigned_students=30, arrival_buffer_minutes=10,
        )
        self.db.add_all([full, spare])
        self.db.commit()

        alternatives = transport_replacements(self.db, full, required_seats=40)

        self.assertEqual(alternatives[0]["bus_id"], spare.bus_id)
        self.assertTrue(alternatives[0]["can_fit"])
        self.assertEqual(alternatives[0]["spare_seats"], 50)

    def test_water_recommendation_only_uses_a_tank_in_the_affected_zone(self):
        outage_node = CampusNode(id="WATER-1", name="Water inlet", node_type="resource", status="failed")
        local_tank_node = CampusNode(
            id="TANK-1", name="Reserve water tank", node_type="resource", status="operational",
        )
        remote_tank_node = CampusNode(
            id="TANK-2", name="Remote water tank", node_type="resource", status="operational",
        )
        outage = Resource(
            node_id=outage_node.id, resource_type="water", zone_id="HOSTEL-A", backup_available=False,
        )
        local_tank = Resource(
            node_id=local_tank_node.id, resource_type="water", zone_id="HOSTEL-A", backup_available=True,
        )
        remote_tank = Resource(
            node_id=remote_tank_node.id, resource_type="water", zone_id="HOSTEL-B", backup_available=True,
        )
        hostel = Hostel(
            id="HOSTEL-1", capacity=100, occupied=80, water_zone="HOSTEL-A",
            power_zone="POWER-A", backup_hours=6,
        )
        self.db.add_all([outage_node, local_tank_node, remote_tank_node, outage, local_tank, remote_tank, hostel])
        self.db.commit()

        recommendation = water_recommendation(self.db, outage)

        self.assertIn("Reserve water tank", recommendation)
        self.assertNotIn("Remote water tank", recommendation)
        self.assertIn("6h", recommendation)

    def test_backup_gap_check_recognizes_mapped_standby_and_uses_review_status(self):
        feeder = CampusNode(
            id="GRID-A", name="Grid feeder A", node_type="resource",
            criticality_label="critical",
        )
        service = CampusNode(id="SERVICE-A", name="Campus service", node_type="service")
        generator = CampusNode(id="GEN-A", name="Standby generator", node_type="resource")
        server = CampusNode(
            id="SERVER-A", name="Database server", node_type="resource",
            criticality_label="critical",
        )
        feeder_resource = Resource(
            node_id=feeder.id, resource_type="electricity", zone_id="POWER-A",
            backup_available=False,
        )
        generator_resource = Resource(
            node_id=generator.id, resource_type="backup_power", zone_id="POWER-A",
            backup_available=True,
        )
        server_resource = Resource(
            node_id=server.id, resource_type="server", zone_id="DATA-A",
            backup_available=False,
        )
        dependency = Dependency(
            id="DEP-A", source_node_id=feeder.id, target_node_id=service.id,
            mitigation_resource_id=generator.id,
        )
        self.db.add_all([
            feeder, service, generator, server, feeder_resource, generator_resource,
            server_resource, dependency,
        ])
        self.db.commit()

        findings = detect_conflicts(self.db)
        backup_gaps = [item for item in findings if item["type"] == "resource_backup_gap"]

        self.assertEqual([item["affected_entities"][0] for item in backup_gaps], [server.id])
        self.assertEqual(backup_gaps[0]["status"], "Needs review")
        self.assertNotIn("critical-critical", backup_gaps[0]["description"])

    def test_operator_assignments_survive_dataset_reseeding(self):
        source_room = Room(id="ROOM-1", building="Main", kind="classroom", capacity=40)
        assigned_room = Room(id="ROOM-2", building="Main", kind="classroom", capacity=40)
        source_faculty = Faculty(
            id="FAC-1", department_id="CSE", designation="Lecturer",
            expertise_course_codes="CS101",
        )
        assigned_faculty = Faculty(
            id="FAC-2", department_id="CSE", designation="Lecturer",
            expertise_course_codes="CS101",
        )
        session = TimetableSession(
            id="SESSION-1", cohort_id="CSE-1", department_id="CSE", course_code="CS101",
            session_type="lecture", room_id=source_room.id, faculty_id=source_faculty.id,
            weekday="Mon", start_time="09:00", duration_hours=1, expected_students=30,
        )
        route = TransportRoute(
            id="ROUTE-1", bus_id="BUS-1", route_name="North", daily_capacity=40,
            assigned_students=20, arrival_buffer_minutes=10,
        )
        self.db.add_all([
            self.department, source_room, assigned_room, source_faculty, assigned_faculty,
            session, route,
        ])
        self.db.flush()
        self.db.add_all([
            TimetableAssignmentOverride(
                session_id=session.id, room_id=assigned_room.id, faculty_id=assigned_faculty.id,
            ),
            TransportRouteAssignmentOverride(route_id=route.id, assigned_students=25),
        ])
        self.db.commit()

        session.room_id = source_room.id
        session.faculty_id = source_faculty.id
        route.assigned_students = 20
        _apply_operational_overrides(self.db)

        self.assertEqual(session.room_id, assigned_room.id)
        self.assertEqual(session.faculty_id, assigned_faculty.id)
        self.assertEqual(route.assigned_students, 25)


if __name__ == "__main__":
    unittest.main()
