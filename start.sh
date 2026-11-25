#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
cd backend
python3 -m venv .venv 2>/dev/null || true
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn main:app --host 127.0.0.1 --port 8000 &
cd ../frontend
npm install
npm run dev -- --host 127.0.0.1 &
sleep 4
if command -v xdg-open >/dev/null; then xdg-open http://localhost:5173; elif command -v open >/dev/null; then open http://localhost:5173; fi
wait
