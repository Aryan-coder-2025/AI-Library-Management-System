@echo off
title Athenaeum AI 2.0 - Launcher
echo ========================================================
echo        ATHENAEUM AI 2.0 - LIBRARY MANAGEMENT SYSTEM
echo ========================================================
echo Starting Backend (FastAPI on Port 8000)...
start "Athenaeum Backend (FastAPI)" cmd /k "cd /d %~dp0backend && ..\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000"

timeout /t 3 /nobreak >nul

echo Starting Frontend (Vite React on Port 5173)...
start "Athenaeum Frontend (Vite)" cmd /k "cd /d %~dp0frontend && npm run dev"

timeout /t 3 /nobreak >nul

echo Opening browser to http://localhost:5173...
start http://localhost:5173

echo ========================================================
echo   System is running!
echo   Frontend: http://localhost:5173
echo   Backend:  http://127.0.0.1:8000/docs
echo ========================================================

