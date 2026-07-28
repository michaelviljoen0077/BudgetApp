#!/usr/bin/env python3
"""
Script to start the Budget App desktop frontend.
Ensure you have installed dependencies: pip install -r requirements.txt
Ensure the backend is running on http://localhost:8000
"""
import subprocess
import sys
import os

def main():
    os.chdir("frontend")
    
    print("Starting Budget App Frontend")
    print("Make sure the backend is running on http://localhost:8000")
    print("\nIf you see a connection error, start the backend first with: python run_backend.py")
    
    try:
        subprocess.run([sys.executable, "main.py"])
    except KeyboardInterrupt:
        print("\n\nFrontend stopped.")
        sys.exit(0)

if __name__ == "__main__":
    main()
