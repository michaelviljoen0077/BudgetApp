#!/usr/bin/env python3
"""
Script to start the Budget App backend service.
Ensure you have installed dependencies: pip install -r requirements.txt
"""
import subprocess
import sys
import os

def main():
    os.chdir("backend")
    
    print("Starting Budget App Backend on http://localhost:8000")
    print("Documentation available at http://localhost:8000/docs")
    print("\nPress Ctrl+C to stop the server")
    
    try:
        subprocess.run([
            sys.executable, "-m", "uvicorn",
            "main:app",
            "--host", "0.0.0.0",
            "--port", "8000",
            "--reload"
        ])
    except KeyboardInterrupt:
        print("\n\nBackend stopped.")
        sys.exit(0)

if __name__ == "__main__":
    main()
