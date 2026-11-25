import unittest

import seed

seed.seed = lambda: None

import main
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.models import Department, Faculty, Room, TimetableSession, TransportRoute
from database import Base


class AssignmentApiTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)
        self.db.add(Department(id="CSE", name="Computer Science"))
        self.db.add_all([
            Room(id="ROOM-1", building="Main", kind="classroom", capacity=30),
            Room(id="ROOM-2", building="Main", kind="classroom", capacity=35),
            Faculty(
                id="FAC-1", department_id="CSE", designation="Lecturer",
                expertise_course_codes="CS101", availability_status="unavailable",
            ),
            Faculty(
                id="FAC-2", department_id="CSE", designation="Lecturer",
                expertise_course_codes="CS101", availability_status="available",
            ),
            TimetableSession(
                id="CLASS-1", cohort_id="CSE-1", department_id="CSE",
                course_code="CS101", session_type="lecture", room_id="ROOM-1",
                faculty_id="FAC-1", weekday="Mon", start_time="09:00",
                duration_hours=1, expected_students=30, status="scheduled",
            ),
            TransportRoute(
                id="ROUTE-1", bus_id="BUS-1", route_name="North",
                daily_capacity=40, assigned_students=40, arrival_buffer_minutes=10,
            ),
            TransportRoute(
                id="ROUTE-2", bus_id="BUS-2", route_name="South",
                daily_capacity=50, assigned_students=10, arrival_buffer_minutes=10,
            ),
        ])
        self.db.commit()

    def test_admin_can_assign_free_room_and_qualified_faculty(self):
        options = main.assignment_options("CLASS-1", _user=object(), db=self.db)
        self.assertEqual([item["id"] for item in options["rooms"]], ["ROOM-2"])
        self.assertEqual([item["id"] for item in options["faculty"]], ["FAC-2"])

        result = main.assign_session(
            "CLASS-1",
            main.SessionAssignmentRequest(room_id="ROOM-2", faculty_id="FAC-2"),
            _user=object(),
            db=self.db,
        )

        self.assertEqual(result["room_id"], "ROOM-2")
        self.assertEqual(result["faculty_id"], "FAC-2")

    def test_admin_can_transfer_riders_only_into_verified_spare_capacity(self):
        result = main.transfer_route_riders(
            "ROUTE-1",
            main.TransportTransferRequest(target_route_id="ROUTE-2", rider_count=20),
            _user=object(),
            db=self.db,
        )

        self.assertEqual(result["source_assigned_students"], 20)
        self.assertEqual(result["target_assigned_students"], 30)
        with self.assertRaises(HTTPException) as raised:
            main.transfer_route_riders(
                "ROUTE-1",
                main.TransportTransferRequest(target_route_id="ROUTE-2", rider_count=21),
                _user=object(),
                db=self.db,
            )
        self.assertEqual(raised.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
