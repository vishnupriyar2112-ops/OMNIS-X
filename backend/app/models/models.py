from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from database import Base


class Department(Base):
    __tablename__ = "departments"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    student_count = Column(Integer, nullable=False, default=0)
    faculty_count = Column(Integer, nullable=False, default=0)
    academic_years = Column(String, nullable=False, default="")
    data_status = Column(String, nullable=False, default="synthetic_demo")
    students = relationship("Student", back_populates="department")
    faculty = relationship("Faculty", back_populates="department")
    rooms = relationship("Room", back_populates="department")


class Student(Base):
    __tablename__ = "students"
    id = Column(String, primary_key=True)
    department_id = Column(String, ForeignKey("departments.id"), nullable=False)
    year = Column(Integer, nullable=False)
    semester = Column(Integer, nullable=False)
    cohort_id = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False, default="active")
    data_status = Column(String, nullable=False, default="synthetic_demo")
    department = relationship("Department", back_populates="students")


class Faculty(Base):
    __tablename__ = "faculty"
    id = Column(String, primary_key=True)
    department_id = Column(String, ForeignKey("departments.id"), nullable=False)
    designation = Column(String, nullable=False)
    expertise_course_codes = Column(Text, nullable=False, default="")
    max_weekly_hours = Column(Integer, nullable=False, default=18)
    availability_status = Column(String, nullable=False, default="available")
    data_status = Column(String, nullable=False, default="synthetic_demo")
    department = relationship("Department", back_populates="faculty")


class CampusNode(Base):
    __tablename__ = "campus_nodes"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    node_type = Column(String, nullable=False)
    criticality = Column(Float, nullable=False, default=0.5)
    criticality_label = Column(String, nullable=False, default="medium")
    status = Column(String, nullable=False, default="operational")
    data_status = Column(String, nullable=False, default="synthetic_demo")
    resource = relationship("Resource", back_populates="node", uselist=False, cascade="all, delete-orphan")
    service = relationship("Service", back_populates="node", uselist=False, cascade="all, delete-orphan")


class Resource(Base):
    __tablename__ = "resources"
    node_id = Column(String, ForeignKey("campus_nodes.id", ondelete="CASCADE"), primary_key=True)
    resource_type = Column(String, nullable=False)
    zone_id = Column(String, nullable=False, default="")
    backup_available = Column(Boolean, nullable=False, default=False)
    node = relationship("CampusNode", back_populates="resource")


class Service(Base):
    __tablename__ = "services"
    node_id = Column(String, ForeignKey("campus_nodes.id", ondelete="CASCADE"), primary_key=True)
    service_type = Column(String, nullable=False)
    node = relationship("CampusNode", back_populates="service")


class Dependency(Base):
    __tablename__ = "dependencies"
    id = Column(String, primary_key=True)
    source_node_id = Column(String, ForeignKey("campus_nodes.id"), nullable=False, index=True)
    target_node_id = Column(String, ForeignKey("campus_nodes.id"), nullable=False, index=True)
    dependency_type = Column(String, nullable=False, default="hard")
    weight = Column(Float, nullable=False, default=1.0)
    mitigation_resource_id = Column(String, ForeignKey("resources.node_id"), nullable=True)
    direction_note = Column(String, nullable=False, default="provider_to_dependent")
    source = relationship("CampusNode", foreign_keys=[source_node_id])
    target = relationship("CampusNode", foreign_keys=[target_node_id])
    mitigation_resource = relationship("Resource", foreign_keys=[mitigation_resource_id])


class Room(Base):
    __tablename__ = "rooms"
    id = Column(String, primary_key=True)
    building = Column(String, nullable=False)
    kind = Column(String, nullable=False)
    capacity = Column(Integer, nullable=False)
    department_id = Column(String, ForeignKey("departments.id"), nullable=True)
    lab_type = Column(String, nullable=False, default="")
    equipment = Column(Text, nullable=False, default="")
    power_zone = Column(String, nullable=False, default="")
    network_zone = Column(String, nullable=False, default="")
    status = Column(String, nullable=False, default="operational")
    data_status = Column(String, nullable=False, default="synthetic_demo")
    department = relationship("Department", back_populates="rooms")


class TimetableSession(Base):
    __tablename__ = "timetable_sessions"
    id = Column(String, primary_key=True)
    cohort_id = Column(String, nullable=False, index=True)
    department_id = Column(String, ForeignKey("departments.id"), nullable=False)
    course_code = Column(String, nullable=False)
    session_type = Column(String, nullable=False)
    room_id = Column(String, ForeignKey("rooms.id"), nullable=False)
    faculty_id = Column(String, ForeignKey("faculty.id"), nullable=False)
    weekday = Column(String, nullable=False)
    start_time = Column(String, nullable=False)
    duration_hours = Column(Float, nullable=False)
    expected_students = Column(Integer, nullable=False)
    status = Column(String, nullable=False, default="scheduled")
    data_status = Column(String, nullable=False, default="synthetic_demo")
    department = relationship("Department")
    room = relationship("Room")
    faculty = relationship("Faculty")


class TimetableAssignmentOverride(Base):
    __tablename__ = "timetable_assignment_overrides"
    session_id = Column(String, ForeignKey("timetable_sessions.id", ondelete="CASCADE"), primary_key=True)
    room_id = Column(String, ForeignKey("rooms.id"), nullable=False)
    faculty_id = Column(String, ForeignKey("faculty.id"), nullable=False)


class Examination(Base):
    __tablename__ = "examinations"
    id = Column(String, primary_key=True)
    cohort_id = Column(String, nullable=False, index=True)
    department_id = Column(String, ForeignKey("departments.id"), nullable=False)
    course_code = Column(String, nullable=False)
    exam_date = Column(Date, nullable=False)
    start_time = Column(String, nullable=False)
    duration_hours = Column(Float, nullable=False)
    room_id = Column(String, ForeignKey("rooms.id"), nullable=False)
    student_count = Column(Integer, nullable=False)
    invigilator_id = Column(String, ForeignKey("faculty.id"), nullable=False)
    exam_mode = Column(String, nullable=False)
    status = Column(String, nullable=False, default="scheduled")
    data_status = Column(String, nullable=False, default="synthetic_demo")
    department = relationship("Department")
    room = relationship("Room")
    invigilator = relationship("Faculty")


class Hostel(Base):
    __tablename__ = "hostels"
    id = Column(String, primary_key=True)
    capacity = Column(Integer, nullable=False)
    occupied = Column(Integer, nullable=False)
    water_zone = Column(String, nullable=False)
    power_zone = Column(String, nullable=False)
    backup_hours = Column(Float, nullable=False, default=0)
    data_status = Column(String, nullable=False, default="synthetic_demo")


class TransportRoute(Base):
    __tablename__ = "transport_routes"
    id = Column(String, primary_key=True)
    bus_id = Column(String, nullable=False)
    route_name = Column(String, nullable=False)
    daily_capacity = Column(Integer, nullable=False)
    assigned_students = Column(Integer, nullable=False)
    arrival_buffer_minutes = Column(Integer, nullable=False)
    data_status = Column(String, nullable=False, default="synthetic_demo")


class TransportRouteAssignmentOverride(Base):
    __tablename__ = "transport_route_assignment_overrides"
    route_id = Column(String, ForeignKey("transport_routes.id", ondelete="CASCADE"), primary_key=True)
    assigned_students = Column(Integer, nullable=False)


class Event(Base):
    __tablename__ = "events"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    event_type = Column(String, nullable=False)
    organizing_department_id = Column(String, nullable=True)
    event_date = Column(Date, nullable=False)
    start_time = Column(String, nullable=False)
    duration_hours = Column(Float, nullable=False)
    venue_id = Column(String, ForeignKey("rooms.id"), nullable=False)
    priority = Column(String, nullable=False)
    data_status = Column(String, nullable=False, default="synthetic_demo")
    venue = relationship("Room")


class FailureScenario(Base):
    __tablename__ = "failure_scenarios"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    root_node_id = Column(String, ForeignKey("campus_nodes.id"), nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    severity_input = Column(String, nullable=False)
    assumption = Column(Text, nullable=False)
    root_node = relationship("CampusNode")


class RecoveryOption(Base):
    __tablename__ = "recovery_options"
    id = Column(String, primary_key=True)
    scenario_family = Column(String, nullable=False)
    action = Column(String, nullable=False)
    required_resource_id = Column(String, nullable=False)
    required_node_id = Column(String, ForeignKey("campus_nodes.id"), nullable=True)
    required_room_id = Column(String, ForeignKey("rooms.id"), nullable=True)
    capacity_limit = Column(String, nullable=False)
    estimated_setup_minutes = Column(Integer, nullable=False)
    direct_cost_units = Column(Float, nullable=False)
    disruption_level = Column(String, nullable=False)
    required_node = relationship("CampusNode")
    required_room = relationship("Room")


class Incident(Base):
    __tablename__ = "incidents"
    id = Column(String, primary_key=True)
    failure_type = Column(String, nullable=False)
    failed_resource = Column(String, nullable=False)
    failed_node_id = Column(String, ForeignKey("campus_nodes.id"), nullable=True)
    timestamp = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer, nullable=False, default=0)
    severity = Column(String, nullable=False)
    impact_score = Column(Float, nullable=False, default=0)
    affected_resources = Column(Text, nullable=False, default="[]")
    recovery_plan = Column(Text, nullable=False, default="")
    resolution_summary = Column(Text, nullable=False, default="")
    restored_at = Column(DateTime, nullable=True)
    resolution_status = Column(String, nullable=False, default="Open")
    is_synthetic = Column(Boolean, nullable=False, default=False)
    failed_node = relationship("CampusNode")


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, nullable=False, unique=True, index=True)
    name = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False, default="administrator")
    is_active = Column(Boolean, nullable=False, default=True)
    is_synthetic = Column(Boolean, nullable=False, default=True)
