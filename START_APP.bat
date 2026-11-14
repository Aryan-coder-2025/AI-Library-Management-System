@echo off
setlocal enabledelayedexpansion
title Athenaeum AI 2.0 - Launcher
cd /d "%~dp0"

echo ========================================================
echo        ATHENAEUM AI 2.0 - LIBRARY MANAGEMENT SYSTEM
echo ========================================================

REM Step 0: Clean up any previous stale processes on ports 8000 / 5173
echo [1/4] Checking and clearing ports 8000 and 5173...
powershell -NoProfile -Command "Get-Process -Id (Get-NetTCPConnection -LocalPort 8000, 5173 -ErrorAction SilentlyContinue).OwningProcess -ErrorAction SilentlyContinue | Stop-Process -Force" >nul 2>&1

echo [2/4] Starting Athenaeum Backend (FastAPI on Port 8000)...
start "Athenaeum Backend (FastAPI)" "%~dp0backend\run_backend.bat"

REM Step 2: Health check backend loop (wait until 127.0.0.1:8000/api/health responds 200)
echo Waiting for Backend API to initialize...
set /a ATTEMPTS=0
:WAIT_BACKEND
ping 127.0.0.1 -n 2 >nul
set /a ATTEMPTS+=1
curl.exe -s -f http://127.0.0.1:8000/api/health >nul 2>&1
if !ERRORLEVEL! equ 0 goto BACKEND_READY
if !ATTEMPTS! geq 25 (
    echo [WARNING] Backend took longer to respond. Proceeding to launch frontend...
    goto LAUNCH_FRONTEND
)
goto WAIT_BACKEND

:BACKEND_READY
echo [OK] Backend API is live and healthy!

:LAUNCH_FRONTEND
REM Step 3: Launch Frontend
echo [3/4] Starting Athenaeum Frontend (Vite on Port 5173)...
start "Athenaeum Frontend (Vite)" "%~dp0frontend\run_frontend.bat"

REM Step 4: Health check frontend loop (wait until localhost:5173 responds)
echo Waiting for Frontend web server to initialize...
set /a F_ATTEMPTS=0
:WAIT_FRONTEND
ping 127.0.0.1 -n 2 >nul
set /a F_ATTEMPTS+=1
curl.exe -s -f http://localhost:5173 >nul 2>&1
if !ERRORLEVEL! equ 0 goto FRONTEND_READY
if !F_ATTEMPTS! geq 15 goto FRONTEND_READY
goto WAIT_FRONTEND

:FRONTEND_READY
echo [OK] Frontend web server is live!

echo [4/4] Opening browser to http://localhost:5173...
start http://localhost:5173

echo ========================================================
echo   Athenaeum AI 2.0 is fully operational!
echo.
echo   Frontend App:   http://localhost:5173
echo   Backend Docs:   http://127.0.0.1:8000/docs
echo.
echo   Demo Login Shortcuts (Use Quick Demo Pre-fill buttons):
echo     * Student:   student1   / StudentPass123!
echo     * Teacher:   teacher1   / TeacherPass123!
echo     * Librarian: librarian1 / AdminPass123!
echo ========================================================
echo Launcher complete. Both servers are active.
ping 127.0.0.1 -n 4 >nul
