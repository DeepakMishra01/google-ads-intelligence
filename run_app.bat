@echo off
REM ============================================================
REM  Google Ads Command Center - one-click launcher
REM  Serves BOTH the backend API and the dashboard UI from a
REM  single process at http://localhost:8000
REM  Auto-restarts if it ever stops. Close this window to stop.
REM ============================================================
title Google Ads Command Center (http://localhost:8000)
cd /d "D:\Google Ads Automation"
set "PYTHONPATH=D:\Google Ads Automation"

REM Build the dashboard UI once if it hasn't been built yet.
if not exist "frontend\dist\index.html" (
    echo Building the dashboard UI for the first time, please wait...
    call npm --prefix frontend run build
)

:loop
echo.
echo ============================================================
echo   Starting Google Ads Command Center...
echo   Open in your browser:  http://localhost:8000
echo   (Close this window to stop the app)
echo ============================================================
echo.
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level warning
echo.
echo  ** Server stopped unexpectedly. Restarting in 3 seconds... **
timeout /t 3 /nobreak >nul
goto loop
