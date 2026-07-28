@echo off
REM Budget App Frontend Startup Script for Windows

echo.
echo 🧾 Budget App Frontend
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
python -c "from PySide6.QtWidgets import QApplication" >nul 2>&1
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
echo Starting Frontend...
echo Make sure the backend is running on http://localhost:8000
echo.

cd /d frontend
python main.py

pause
