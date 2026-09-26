#!/usr/bin/env python3
"""Start the backend, wait until it is healthy, then open the desktop UI. Closing the UI stops both."""
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HEALTH_URL = "http://127.0.0.1:8000/health"


def backend_is_healthy() -> bool:
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=1) as response:
            return response.status == 200
    except OSError:
        return False


def main():
    backend = None
    if backend_is_healthy():
        print("Backend already running.")
    else:
        print("Starting backend...")
        backend = subprocess.Popen([sys.executable, str(ROOT / "run_backend.py")])
        for _ in range(20):
            if backend_is_healthy():
                break
            if backend.poll() is not None:
                sys.exit("Backend exited during startup; run `python run_backend.py` to see why.")
            time.sleep(0.5)
        else:
            backend.terminate()
            sys.exit("Backend did not become healthy within 10 seconds.")

    try:
        subprocess.run([sys.executable, str(ROOT / "run_frontend.py")])
    except KeyboardInterrupt:
        pass
    finally:
        if backend and backend.poll() is None:
            print("Stopping backend...")
            backend.terminate()
            try:
                backend.wait(timeout=5)
            except subprocess.TimeoutExpired:
                backend.kill()


if __name__ == "__main__":
    main()
