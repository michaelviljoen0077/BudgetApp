@echo off
REM Budget App Launcher - Runs both backend and frontend

echo.
echo 🧾 Budget App Launcher
echo ========================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python not found
    pause
    exit /b 1
)

echo 📡 Starting backend server...
start "Budget App Backend" cmd /k "python run_backend.py"

echo ⏳ Waiting for backend to start...
timeout /t 3 /nobreak >nul

echo.
echo 🖥️  Starting frontend...
python run_frontend.py

echo.
echo ✅ Budget App stopped
pause
