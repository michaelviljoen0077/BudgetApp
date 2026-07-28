#!/usr/bin/env python3
"""
Launch both backend and frontend for Budget App.
Starts backend server, then opens desktop UI.
"""
import subprocess
import sys
import os
import time
import requests
from pathlib import Path

def check_backend_health(max_attempts=10):
    """Check if backend is responding."""
    url = "http://localhost:8000/health"
    for i in range(max_attempts):
        try:
            response = requests.get(url, timeout=1)
            if response.status_code == 200:
                return True
        except requests.exceptions.RequestException:
            pass
        time.sleep(1)
    return False

def main():
    print("🧾 Budget App Launcher")
    print("=" * 50)
    
    backend_process = None
    
    try:
        # Start backend in subprocess
        print("\n📡 Starting backend server...")
        backend_process = subprocess.Popen(
            [sys.executable, "run_backend.py"],
            cwd=Path(__file__).parent
        )
        
        # Wait for backend to start and respond
        print("⏳ Waiting for backend to start...")
        if not check_backend_health():
            print("❌ Backend failed to start or is not responding")
            print("   Try running manually: python run_backend.py")
            sys.exit(1)
        
        print("✅ Backend running on http://localhost:8000")
        
        # Start frontend in main process
        print("\n🖥️  Starting frontend...")
        frontend_process = subprocess.Popen(
            [sys.executable, "run_frontend.py"],
            cwd=Path(__file__).parent
        )
        
        print("✅ Frontend launched")
        print("\n🎉 Budget App is running!")
        print("   Backend:  http://localhost:8000")
        print("   API Docs: http://localhost:8000/docs")
        print("\nPress Ctrl+C to stop both services")
        
        # Wait for frontend to close
        frontend_process.wait()
        
    except KeyboardInterrupt:
        print("\n\n⏹️  Stopping Budget App...")
    
    finally:
        # Clean up processes
        if backend_process and backend_process.poll() is None:
            print("Stopping backend...")
            backend_process.terminate()
            try:
                backend_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                backend_process.kill()
        
        print("✅ Budget App stopped")

if __name__ == "__main__":
    main()
