# 🔧 Troubleshooting Guide

Common issues and how to fix them.

## Installation Issues

### "Python not found" or "python is not recognized"

**Cause:** Python not in PATH or not installed

**Fix:**
1. Install Python from https://www.python.org/downloads/
2. During installation, **check "Add Python to PATH"**
3. Restart terminal/command prompt
4. Verify: `python --version`

---

### "pip: command not found"

**Cause:** Python installed but pip not available

**Fix:**
```bash
# Linux/Mac
python3 -m ensurepip --upgrade

# Windows
python -m ensurepip --upgrade
```

---

### "Permission denied" when running setup.py

**Cause:** File permissions issue

**Fix:**
```bash
# Linux/Mac
chmod +x setup.py
python setup.py

# Windows
# Run as Administrator or use:
python setup.py
```

---

## Dependency Issues

### "ModuleNotFoundError: No module named 'fastapi'"

**Cause:** Backend dependencies not installed

**Fix:**
```bash
cd backend
pip install -r requirements.txt
```

---

### "ModuleNotFoundError: No module named 'PySide6'"

**Cause:** Frontend dependencies not installed

**Fix:**
```bash
cd frontend
pip install -r requirements.txt
```

---

### Can't install PySide6 on Windows

**Cause:** Missing Visual C++ Build Tools

**Fix:**
1. Download Visual Studio C++ Build Tools
2. Install (minimal selection is fine)
3. Retry: `pip install PySide6`

**Alternative:**
```bash
# Use pre-built wheel
pip install --only-binary :all: PySide6
```

---

### Can't install PySide6 on macOS

**Cause:** Xcode command line tools missing

**Fix:**
```bash
xcode-select --install
pip install PySide6
```

---

### Can't install PySide6 on Linux

**Cause:** Missing Qt development packages

**Fix:**

**Ubuntu/Debian:**
```bash
sudo apt install libqt6core6 libqt6gui6 libqt6widgets6
pip install PySide6
```

**Fedora:**
```bash
sudo dnf install qt6-qtbase qt6-qtdeclarative
pip install PySide6
```

**Arch:**
```bash
sudo pacman -S qt6-base qt6-declarative
pip install PySide6
```

---

## Backend Issues

### "Address already in use" or "Port 8000 in use"

**Cause:** Another process using port 8000

**Fix 1 (stop other process):**
```bash
# Linux/Mac
lsof -i :8000
kill -9 <PID>

# Windows PowerShell
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

**Fix 2 (change port):**

Edit `run_backend.py`:
```python
"--port", "9000",  # Change from 8000 to 9000
```

Then update frontend in `frontend/main.py`:
```python
self.client = BudgetAppClient(base_url="http://localhost:9000")
```

---

### Backend starts but immediately stops

**Cause:** Error in main.py or missing data directory

**Fix:**
```bash
cd backend
python -c "import main"  # Check for syntax errors
mkdir data               # Ensure data directory exists
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

---

### Backend runs but returns 500 errors

**Cause:** Error in API code

**Fix:**
1. Check backend terminal for error messages
2. Look for exceptions and tracebacks
3. Check `backend/data/` directory exists and is writable
4. Verify JSON files are valid: `python -m json.tool backend/data/*.json`

---

### "Connection refused" when accessing http://localhost:8000

**Cause:** Backend not running or different port

**Fix:**
1. Make sure backend is running: `python run_backend.py`
2. Check the terminal output for the actual port
3. Try http://localhost:8000/health to test connection

---

## Frontend Issues

### Frontend crashes immediately on startup

**Cause:** Can't connect to backend

**Fix:**
1. Start backend first: `python run_backend.py`
2. Wait for "Uvicorn running" message
3. Then start frontend

---

### "Cannot connect to backend" message in app

**Cause:** Backend not running or wrong URL

**Fix:**
1. Verify backend is running: `curl http://localhost:8000/health`
2. Check frontend is trying to connect to correct URL
3. If using different port, update in `frontend/main.py`:
   ```python
   self.client = BudgetAppClient(base_url="http://localhost:8000")
   ```

---

### Frontend window doesn't display correctly

**Cause:** Qt platform issues or display server issues (especially Linux)

**Fix:**

**Linux with X11:**
```bash
export QT_QPA_PLATFORM=xcb
python frontend/main.py
```

**Linux with Wayland:**
```bash
export QT_QPA_PLATFORM=wayland
python frontend/main.py
```

**macOS with M1/M2:**
```bash
# May need native ARM build of PySide6
pip uninstall PySide6
pip install --no-cache PySide6
```

---

### Buttons/UI elements not responding

**Cause:** Frontend is waiting for slow backend operation

**Fix:**
1. The UI should still be responsive (async operations)
2. If frozen, backend may be slow
3. Check backend logs for errors
4. Restart both backend and frontend

---

## Data Issues

### Data not persisting (deleted when app restarts)

**Cause:** Data directory issue or JSON write failure

**Fix:**
1. Verify `backend/data/` directory exists:
   ```bash
   ls -la backend/data/
   ```
2. Check file permissions:
   ```bash
   chmod 755 backend/data/
   chmod 644 backend/data/*.json
   ```
3. Check backend logs for write errors
4. Try importing a transaction and checking if JSON file is updated

---

### "Permission denied" writing to data files

**Cause:** File permissions issue

**Fix:**
```bash
# Linux/Mac
chmod 755 backend/data/
chmod 644 backend/data/*.json

# Windows (run in admin)
icacls "backend\data" /grant:r "%USERNAME%":F
```

---

### JSON files corrupted or invalid

**Cause:** Incomplete write or manual editing error

**Fix:**
```bash
# Backup corrupted files
mv backend/data/ledger.json backend/data/ledger.json.bak

# Restart backend - it will create fresh files
python run_backend.py
```

---

### Can't import CSV file

**Cause:** CSV format not recognized

**Fix:**
1. Verify CSV has columns: Date, Description, Amount
2. Check date format is standard (e.g., 2024-01-15 or 1/15/2024)
3. Check amounts are numbers (no $ symbol or spaces)
4. See [CONFIGURATION.md](CONFIGURATION.md) to add custom bank format

**Test CSV parsing:**
```python
import csv
with open('your_file.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        print(row)
```

---

## Performance Issues

### Backend is slow with large data

**Cause:** Scanning large JSON file for every request

**Fix:**
1. That's expected with JSON storage and large datasets
2. Consider migrating to database (see [DEVELOPMENT.md](DEVELOPMENT.md))
3. Use pagination: add `limit=10` to requests
4. Filter data: add `category_path` or date filters

---

### Frontend UI freezes when loading many transactions

**Cause:** Rendering many table rows at once

**Fix:**
1. Use pagination in the API: `skip=0&limit=50`
2. The frontend already does this, check browser console for errors
3. Try scrolling – tables are virtualized

---

## API Issues

### API returns 404 "Not found"

**Cause:** Wrong endpoint URL

**Fix:**
1. Check the endpoint is correct (see [README.md](README.md) API Reference)
2. Verify backend is running
3. Try http://localhost:8000/docs for interactive API explorer

---

### API returns 400 "Bad request"

**Cause:** Invalid request data

**Fix:**
1. Check all required fields are provided
2. Verify date format is ISO (2024-01-15T00:00:00)
3. Verify amounts are numbers
4. Check the request body matches the model

Example valid transaction:
```json
{
  "date": "2024-01-15T10:30:00",
  "description": "Coffee",
  "amount": 5.50,
  "currency": "USD",
  "transaction_type": "expense"
}
```

---

### Categories endpoint returns empty

**Cause:** Categories not initialized

**Fix:**
1. Restart backend – it initializes defaults on startup
2. Check that `backend/data/categories.json` exists
3. Try creating a category:
   ```bash
   curl -X POST http://localhost:8000/categories \
     -H "Content-Type: application/json" \
     -d '{"name":"Test","parent_id":null}'
   ```

---

## Configuration Issues

### Can't connect to AI service

**Cause:** Local LLM not running or wrong URL

**Fix (for local LLM):**
1. Start your LLM service:
   ```bash
   ollama serve  # or LM Studio
   ```
2. Verify it's running on localhost:8001
3. Update backend if using different port

---

### Environment variables not working

**Cause:** Variable not set in correct scope

**Fix:**

**Linux/Mac (bash):**
```bash
export OPENAI_API_KEY="sk-..."
python run_backend.py
```

**Linux/Mac (zsh):**
```bash
export OPENAI_API_KEY="sk-..."
python run_backend.py
```

**Windows (PowerShell):**
```powershell
$env:OPENAI_API_KEY="sk-..."
python run_backend.py
```

**Windows (CMD):**
```cmd
set OPENAI_API_KEY=sk-...
python run_backend.py
```

---

## Backup/Restore Issues

### Can't restore from backup

**Cause:** Corrupted backup files

**Fix:**
1. Validate backup JSON files:
   ```bash
   python -m json.tool backend/data/ledger.json > /dev/null
   ```
2. If valid, restore:
   ```bash
   cp backend/data.backup/* backend/data/
   ```
3. If not valid, use older backup

---

## Windows-Specific Issues

### .bat files won't run

**Cause:** Execution policy or file association

**Fix 1 (double-click):**
- Right-click .bat file
- Select "Open with" → "Command Prompt" or "PowerShell"

**Fix 2 (command line):**
```cmd
python run_backend.py
```

**Fix 3 (execution policy):**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

---

### Unicode/encoding errors in CSV import

**Cause:** CSV file uses different encoding

**Fix (in backend/main.py):**
```python
with open(file_path, 'r', encoding='utf-8') as f:  # or 'latin-1', 'cp1252', etc.
    csv_content = f.read()
```

---

## macOS-Specific Issues

### "Cannot open" error when running .app

**Cause:** Not a real app, it's Python code

**Fix:**
```bash
python run_backend.py
python run_frontend.py  # new terminal
```

---

### Permission denied errors

**Cause:** File permissions

**Fix:**
```bash
chmod +x run_backend.py run_frontend.py setup.py
python setup.py
```

---

## Linux-Specific Issues

### Display server issues with remote X11

**Cause:** Qt needs display server

**Fix:**
```bash
export DISPLAY=:0  # Your X11 display number
python run_frontend.py
```

Or use SSH with X11 forwarding:
```bash
ssh -X user@host
```

---

## Still Need Help?

1. **Check the logs:**
   - Backend terminal output
   - Browser console (for web frontends)
   - Application logs

2. **Test the API directly:**
   ```bash
   curl http://localhost:8000/health
   curl http://localhost:8000/transactions
   ```

3. **Check file permissions:**
   ```bash
   ls -la backend/data/
   ```

4. **Verify configuration:**
   - Check [CONFIGURATION.md](CONFIGURATION.md)
   - Verify backend/frontend URLs match
   - Check port numbers

5. **Read the documentation:**
   - [README.md](README.md) – Features and usage
   - [DEVELOPMENT.md](DEVELOPMENT.md) – Technical details
   - Code comments in `.py` files

---

**If you're still stuck:**
1. Note the exact error message
2. Check the backend logs for details
3. Verify all installation steps completed
4. Try reinstalling: `python setup.py`
5. Review [QUICKSTART.md](QUICKSTART.md) installation steps

---

**Happy debugging!** 🐛
