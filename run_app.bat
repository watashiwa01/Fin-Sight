@echo off
echo Starting Intelli-Credit AI Engine...
echo -----------------------------------
echo 1. Launching FastAPI Backend (api.py)
echo 2. Opening http://localhost:8140 in your browser
echo -----------------------------------

:: Check if python is in path
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python not found. Please install Python to run this app.
    pause
    exit /b
)

:: Start the browser with a small delay
start "" "http://localhost:8140"

:: Run the backend
python api.py

pause
