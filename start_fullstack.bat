@echo off
TITLE Missing Person AI - Full-Stack Launcher
echo ======================================================================
echo           MISSING PERSON AI: 3-MODEL COMPARATIVE SYSTEM
echo ======================================================================
echo.

echo [1/2] Starting FastAPI Backend on http://127.0.0.1:8000 ...
start "Missing Person AI - Backend" cmd /k "cd backend && ..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

timeout /t 3 /nobreak >nul

echo [2/2] Starting Vite Frontend on http://localhost:5173 ...
start "Missing Person AI - Frontend" cmd /k "cd frontend && npm run dev"

echo.
echo ======================================================================
echo Services started!
echo - Frontend Web Application: http://localhost:5173/
echo - Backend REST API Root:    http://127.0.0.1:8000/api/
echo - Interactive Swagger Docs: http://127.0.0.1:8000/docs
echo ======================================================================
echo.
pause
