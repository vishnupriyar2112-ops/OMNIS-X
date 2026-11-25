"""Deterministic generator for the OMNIS-X sample institution.

Pure Python (no database). `build()` returns a dict of table-name -> list of row dicts.
The timetable is produced by a conflict-free scheduler; a small, explicit set of
conflicts is then planted (see PLANTED below) so the *detection* engine has real
problems to find. The detector itself does not know about these plants.
"""
import random
from datetime import date, timedelta

SEED = 2026

DEPT_DEFS = [
    ("CSE", "Computer Science & Engineering", "Block A"),
    ("ECE", "Electronics & Communication Engineering", "Block B"),
    ("EEE", "Electrical & Electronics Engineering", "Block C"),
    ("MECH", "Mechanical Engineering", "Block D"),
]

FACULTY_NAMES = {
    "CSE": ["Dr. Ananya Rao", "Prof. Karthik Menon", "Dr. Sunita Verma", "Prof. Rahul Deshpande", "Dr. Meera Iyer", "Prof. Arjun Nair"],
    "ECE": ["Dr. Vikram Sethi", "Prof. Lakshmi Narayanan", "Dr. Farhan Qureshi", "Prof. Divya Pillai", "Dr. Suresh Babu", "Prof. Nandini Kulkarni"],
    "EEE": ["Dr. Rajesh Khanna", "Prof. Pooja Malhotra", "Dr. Harish Chandra", "Prof. Anita Joshi", "Dr. Manoj Tiwari", "Prof. Shweta Bhat"],
    "MECH": ["Dr. Gopal Krishnan", "Prof. Ritu Agarwal", "Dr. Imran Sheikh", "Prof. Deepa Reddy", "Dr. Satish Kumar", "Prof. Kavya Hegde"],
}

# per dept, per year: 4 theory subjects + 1 lab.  Names starting with '*' are shared across depts.
CATALOG = {
    "CSE": {
        1: (["*Programming in C", "*Engineering Mathematics I", "*Engineering Physics", "*Basic Electrical Engineering"], "Programming Lab"),
        2: (["Data Structures", "Discrete Mathematics", "Digital Logic Design", "Object Oriented Programming"], "Data Structures Lab"),
        3: (["Operating Systems", "Database Management Systems", "Computer Networks", "Theory of Computation"], "DBMS Lab"),
        4: (["Machine Learning", "Cloud Computing", "Information Security", "Software Engineering"], "ML Lab"),
    },
    "ECE": {
        1: (["*Programming in C", "*Engineering Mathematics I", "*Engineering Physics", "Basic Electronics"], "Electronics Workshop"),
        2: (["Network Analysis", "Analog Circuits", "Signals and Systems", "Electromagnetic Theory"], "Analog Circuits Lab"),
        3: (["Digital Signal Processing", "Communication Systems", "Microprocessors", "VLSI Design"], "Communication Lab"),
        4: (["Wireless Networks", "Embedded Systems", "Antenna Theory", "Optical Communication"], "Embedded Systems Lab"),
    },
    "EEE": {
        1: (["*Engineering Mathematics I", "*Engineering Physics", "*Basic Electrical Engineering", "*Engineering Graphics"], "Electrical Workshop"),
        2: (["Circuit Theory", "Electrical Machines I", "Analog Electronics", "Control Systems"], "Machines Lab I"),
        3: (["Power Systems I", "Electrical Machines II", "Power Electronics", "Measurements and Instruments"], "Power Electronics Lab"),
        4: (["Power System Protection", "Renewable Energy Systems", "HVDC Transmission", "Electric Drives"], "Drives Lab"),
    },
    "MECH": {
        1: (["*Engineering Mathematics I", "*Engineering Physics", "Engineering Mechanics", "*Engineering Graphics"], "Workshop Practice"),
        2: (["Thermodynamics", "Fluid Mechanics", "Strength of Materials", "Manufacturing Processes"], "Fluid Mechanics Lab"),
        3: (["Heat Transfer", "Machine Design", "Dynamics of Machinery", "Metrology"], "Thermal Engineering Lab"),