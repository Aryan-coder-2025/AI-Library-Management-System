@echo off
title Athenaeum AI 2.0 - Stopper
echo ========================================================
echo        ATHENAEUM AI 2.0 - SHUTDOWN UTILITY
echo ========================================================
echo Stopping Athenaeum Backend (Port 8000) and Frontend (Port 5173)...

REM Terminate any process on port 8000 (Backend FastAPI)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000" ^| findstr "LISTENING"') do (
    echo Stopping Backend process with PID: %%a
    taskkill /F /PID %%a >nul 2>&1
)

REM Terminate any process on port 5173 (Frontend Vite)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5173" ^| findstr "LISTENING"') do (
    echo Stopping Frontend process with PID: %%a
    taskkill /F /PID %%a >nul 2>&1
)

REM Secondary cleanup for python uvicorn and node processes if any remain
taskkill /F /FI "WINDOWTITLE eq Athenaeum Backend (FastAPI)*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Athenaeum Frontend (Vite)*" >nul 2>&1

echo ========================================================
echo   Application successfully stopped!
echo   Ports 8000 and 5173 are now completely free.
echo ========================================================
pause
