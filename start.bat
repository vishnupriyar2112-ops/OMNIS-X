@echo off
setlocal
cd /d "%~dp0"
echo Starting OMNIS-X setup...
cd backend
if not exist .venv (
  py -3.12 -m venv .venv
)
call ".venv\Scripts\activate.bat"
python -m pip install -r requirements.txt
start "OMNIS-X API" cmd /k "cd /d ""%~dp0backend"" && call "".venv\Scripts\activate.bat"" && python -m uvicorn main:app --host 0.0.0.0 --port 8000"
cd ..\frontend
if not exist node_modules (
  call npm install
)
start "OMNIS-X Web" cmd /k "cd /d ""%~dp0frontend"" && npm run dev -- --host 0.0.0.0 --strictPort"
timeout /t 4 /nobreak >nul
start http://localhost:5173
