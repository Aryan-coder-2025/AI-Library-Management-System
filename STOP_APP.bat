@echo off
title Athenaeum AI 2.0 - Stopper
echo ========================================================
echo        ATHENAEUM AI 2.0 - SHUTDOWN UTILITY
echo ========================================================
echo Stopping Athenaeum Backend (Port 8000) and Frontend (Port 5173)...

REM 1. Stop any process bound to ports 8000 or 5173 using PowerShell
powershell -NoProfile -Command "Get-Process -Id (Get-NetTCPConnection -LocalPort 8000, 5173 -ErrorAction SilentlyContinue).OwningProcess -ErrorAction SilentlyContinue | Stop-Process -Force" >nul 2>&1

REM 2. Fallback netstat cleanup
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000" ^| findstr "LISTENING"') do (
    taskkill /F /T /PID %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5173" ^| findstr "LISTENING"') do (
    taskkill /F /T /PID %%a >nul 2>&1
)

REM 3. Close leftover cmd windows
taskkill /F /T /FI "WINDOWTITLE eq Athenaeum Backend*" >nul 2>&1
taskkill /F /T /FI "WINDOWTITLE eq Athenaeum Frontend*" >nul 2>&1

echo ========================================================
echo   Application successfully stopped!
echo   Ports 8000 and 5173 are now completely free.
echo ========================================================
if not "%1"=="/quiet" (
    pause
)
