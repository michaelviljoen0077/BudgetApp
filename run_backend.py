#!/usr/bin/env python3
"""Start the Budget App backend on http://localhost:8000 (API docs at /docs)."""
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent / "backend"


def main():
    print("Starting Budget App backend on http://localhost:8000 (docs: http://localhost:8000/docs)")
    print("Press Ctrl+C to stop.\n")
    try:
        subprocess.run(
            [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000", *sys.argv[1:]],
            cwd=BACKEND_DIR,
        )
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
