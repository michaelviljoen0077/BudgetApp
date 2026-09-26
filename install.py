#!/usr/bin/env python3
"""Install Budget App dependencies (backend + frontend) into the current Python."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    if sys.version_info < (3, 9):
        sys.exit("Python 3.9+ is required")

    for part in ("backend", "frontend"):
        print(f"Installing {part} dependencies...")
        result = subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(ROOT / part / "requirements.txt")])
        if result.returncode != 0:
            sys.exit(f"Failed to install {part} dependencies")

    print("\nDone. Start the app with:  python run_app.py")


if __name__ == "__main__":
    main()
