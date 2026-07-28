#!/usr/bin/env python3
"""
One-time setup script for Budget App.
Installs all dependencies and initializes data directories.
"""
import subprocess
import sys
import os
from pathlib import Path

def main():
    print("🧾 Budget App Setup")
    print("=" * 50)
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ required")
        sys.exit(1)
    
    print("✓ Python version OK")
    
    # Install backend dependencies
    print("\n📦 Installing backend dependencies...")
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install",
            "-r", "backend/requirements.txt", "-q"
        ])
        print("✓ Backend dependencies installed")
    except subprocess.CalledProcessError:
        print("❌ Failed to install backend dependencies")
        sys.exit(1)
    
    # Install frontend dependencies
    print("\n📦 Installing frontend dependencies...")
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install",
            "-r", "frontend/requirements.txt", "-q"
        ])
        print("✓ Frontend dependencies installed")
    except subprocess.CalledProcessError:
        print("❌ Failed to install frontend dependencies")
        sys.exit(1)
    
    # Create data directory
    data_dir = Path("backend/data")
    data_dir.mkdir(parents=True, exist_ok=True)
    print("✓ Data directory created")
    
    print("\n" + "=" * 50)
    print("✅ Setup complete!")
    print("\n📚 Quick start:")
    print("  1. Start backend:  python run_backend.py")
    print("  2. Start frontend: python run_frontend.py (in new terminal)")
    print("\n📖 For more info, see README.md")

if __name__ == "__main__":
    main()
