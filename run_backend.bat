@echo off
REM Budget App - backend only (http://localhost:8000, docs at /docs)
cd /d "%~dp0"
python --version >nul 2>&1 || (echo Python not found. Install Python 3.9+ from https://www.python.org/downloads/ & pause & exit /b 1)
python -c "import fastapi" >nul 2>&1 || python install.py || (pause & exit /b 1)
python run_backend.py
pause
