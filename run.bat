@echo off
title Aegis CRM HCP Launcher
echo ==========================================================
echo           Aegis CRM - HCP Interaction Module             
echo ==========================================================
echo.
echo Launching full-stack environment...
echo.

:: Launch Backend FastAPI
echo [1/2] Starting Python FastAPI backend on http://localhost:8000...
start "Aegis CRM Backend (FastAPI)" cmd /k "cd backend && venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

:: Wait 3 seconds for backend to initialize
timeout /t 3 /nobreak >null

:: Launch Frontend Vite React
echo [2/2] Starting React Vite frontend on http://localhost:5173...
start "Aegis CRM Frontend (Vite)" cmd /k "cd frontend && npm run dev"

echo.
echo Both terminal windows are running. 
echo - Backend: http://localhost:8000 (API & Docs)
echo - Frontend: http://localhost:5173 (CRM Interface)
echo.
echo Press any key to stop this installer monitoring prompt...
pause >null
