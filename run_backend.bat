@echo off
REM Budget App Backend Startup Script for Windows

echo.
echo 🧾 Budget App Backend
echo ==========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.8+
    echo Visit: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo ✓ Python found

REM Check if dependencies are installed
python -c "import fastapi" >nul 2>&1
if errorlevel 1 (
    echo.
    echo ⚠️  Dependencies not installed. Running setup...
    python setup.py
    if errorlevel 1 (
        echo ERROR: Setup failed
        pause
        exit /b 1
    )
)

echo.
echo Starting Backend on http://localhost:8000
echo API Documentation: http://localhost:8000/docs
echo.
echo Press Ctrl+C to stop
echo.

cd /d backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

pause
