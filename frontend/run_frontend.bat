@echo off
title Athenaeum Frontend (Vite - Port 5173)
cd /d "%~dp0"

echo ========================================================
echo   Athenaeum AI Frontend Interface (Vite on Port 5173)
echo ========================================================

call npm run dev

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Frontend server terminated with exit code %ERRORLEVEL%.
    pause
)
