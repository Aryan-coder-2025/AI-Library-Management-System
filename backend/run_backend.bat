@echo off
title Athenaeum Backend (FastAPI - Port 8000)
cd /d "%~dp0"

echo ========================================================
echo   Athenaeum AI Backend Engine (FastAPI on Port 8000)
echo ========================================================

if exist "%~dp0..\venv\Scripts\python.exe" (
    "%~dp0..\venv\Scripts\python.exe" -m uvicorn app.main:app --app-dir "%~dp0." --host 127.0.0.1 --port 8000
) else if exist "..\venv\Scripts\python.exe" (
    "..\venv\Scripts\python.exe" -m uvicorn app.main:app --app-dir "%~dp0." --host 127.0.0.1 --port 8000
) else (
    python.exe -m uvicorn app.main:app --app-dir "%~dp0." --host 127.0.0.1 --port 8000
)

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Backend process terminated with exit code %ERRORLEVEL%.
    pause
)
