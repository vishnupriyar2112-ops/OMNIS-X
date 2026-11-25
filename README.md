# OMNIS-X

OMNIS-X is a hackathon-ready institutional digital twin and cascading failure recovery prototype for an engineering college.

## Demo credentials

- Email: `admin@omnisx.com`
- Password: `Omnis@123`

## Quick start on Windows

1. Extract the project.
2. Open the project folder in VS Code.
3. Run `start.bat`.
4. Open `http://localhost:5173`.

## Manual start

Backend:

```powershell
cd backend
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Frontend:

```powershell
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --strictPort
```

The Vite server proxies `/api` requests to the backend on port `8000`. Restart the frontend server after changing `vite.config.js`.

## Main URLs

- Application: `http://localhost:5173`
- API documentation: `http://localhost:8000/docs`
- Health and dashboard API: `http://localhost:8000/api/dashboard`

## Prototype scope

The cascade and recovery demonstrations use deterministic, inspectable sample assumptions. Recovery ranking is a rule-based constraint demonstration, not a claim of optimal real-world planning.

## Scheduling and campus recommendations

In **Scheduling & Transport** (administrator access), select a scheduled class or lab and choose an available compatible room and/or qualified faculty member. The page also supports moving a rider count to another route only when that route has enough recorded spare seats; the demo data does not identify individual students on buses. In **Conflict Detection**, review timetable, event-venue, transport-capacity, and resource warnings. Use **Check an event before booking** to compare a proposed date, time, and venue with existing events, examinations, and classes; this check does not create or reserve an event. Where a classroom, lab, or qualified faculty replacement is available, an administrator can use **Apply validated fix** to recheck and save that timetable change. Transport and hostel-water recommendations use only recorded spare seats and water-buffer data, so verify them against current campus operations before acting. All bundled schedules, organizers, and capacities are synthetic demo data.
