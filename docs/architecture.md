# OMNIS-X Architecture

The frontend is a React/Vite single-page application. The backend is a FastAPI service backed by SQLite and SQLAlchemy.

## Data flow

1. `seed.py` initializes four departments, 120 students, 24 faculty, rooms, resources and dependencies.
2. FastAPI routes expose dashboard, twin, dependency, conflict, simulation, incident and recovery data.
3. The React application consumes REST APIs and presents command-centre views.
4. Simulated incidents are persisted in SQLite.

## Cascade model

A simulated failure starts at a selected resource root. Direct and second-order nodes are marked affected by scenario-specific dependency data. Impact scores combine node breadth, affected population and outage duration. Values are simulated indicators, not predictive probabilities.
