@echo off
REM Budget App - starts the backend and the desktop UI
cd /d "%~dp0"
python --version >nul 2>&1 || (echo Python not found. Install Python 3.9+ from https://www.python.org/downloads/ & pause & exit /b 1)
python -c "import fastapi, PySide6" >nul 2>&1 || python install.py || (pause & exit /b 1)
python run_app.py
