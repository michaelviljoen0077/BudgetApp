#!/usr/bin/env python3
"""Start the Budget App desktop UI. The backend must already be running."""
import subprocess
import sys
from pathlib import Path

FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"


def main():
    try:
        subprocess.run([sys.executable, "main.py"], cwd=FRONTEND_DIR)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
