# OMNIS-X Realistic Synthetic Campus Dataset (v1)

## Purpose
A medium-scale, realistic engineering-college dataset for the OMNIS-X A01 institutional digital twin prototype.

## Important provenance notice
All people, IDs, schedules, facilities, incidents, capacities, and operational assumptions in this package are synthetic demonstration data. This is NOT a real college's private or official dataset. It is designed to resemble a plausible engineering institution without identifying real students or staff.

## Scale
- 6 departments: CSE, ISE, AIML, ECE, EEE, MECH
- 1,200 synthetic students (50 per department/year, 4 years)
- 60 synthetic faculty
- 28 rooms/spaces (18 classrooms, 6 labs, 2 exam halls, library, placement hall)
- 22 infrastructure resources
- 15 service/operation nodes
- Directed provider-to-dependent dependency graph
- 48 timetable sessions
- 12 exam records
- 3 hostel blocks
- 4 transport routes
- 3 campus events
- 24 synthetic incident records
- 5 failure scenario definitions
- 6 candidate recovery actions

## Files
See data_dictionary.csv for each file's purpose and relationships.

## Graph semantics
dependencies.csv uses provider -> dependent direction. If a provider fails, the engine traverses outgoing edges to find potentially affected nodes. A real simulation must additionally evaluate redundancy, backup capacity, edge type, and service-level constraints. Structural reachability alone is not proof of actual service failure.

## Suggested integration
1. Load CSVs into normalized relational tables.
2. Validate all foreign keys and graph node references.
3. Build a Campus snapshot from the database.
4. Run dependency propagation from scenario root_node_id.
5. Calculate affected cohorts using timetable_sessions.csv and examinations.csv.
6. Generate recovery candidates from recovery_options.csv.
7. Reject candidates violating capacity, equipment, timetable, faculty, or dependency constraints.
8. Rank remaining candidates using a transparent multi-objective score.

## Limitations
The sample timetable is a compact demonstration schedule, not a complete semester timetable. Scenario assumptions and incident history are synthetic. Before making real operational claims, calibrate capacities, backup coverage, durations, and criticality with authorized campus data.
