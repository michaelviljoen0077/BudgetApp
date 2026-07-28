# 🔧 Budget App Configuration Guide

This guide explains how to configure the Budget App for different setups.

## Backend Configuration

### Default Categories

To customize the default categories that appear when you first run the app, edit `backend/main.py` and modify the `init_categories()` function:

```python
@app.on_event("startup")
async def init_categories():
    default_categories = [
        {
            "name": "Your Category",
            "icon": "🎯",
            "color": "#FF6B6B",
            "children": [
                {"name": "Subcategory", "icon": "📌"},
            ]
        },
        # Add more...
    ]
```

### Bank CSV Format

The default CSV parser expects columns: `Date`, `Description`, `Amount`.

To support your bank's format, edit `backend/main.py` in the `import_bank_csv` endpoint:

```python
@app.post("/imports/bank-csv")
async def import_bank_csv(req: BankImportRequest):
    csv_reader = csv.DictReader(io.StringIO(req.file_content))
    
    for row in csv_reader:
        # Customize field names for your bank
        date_str = row.get("Your Date Field Name")
        description = row.get("Your Description Field")
        amount_str = row.get("Your Amount Field")
```

Example for Chase CSV:
```python
date_str = row.get("Transaction Date")
description = row.get("Description")
amount_str = row.get("Amount")
```

### Data Directory

By default, JSON files are stored in `backend/data/`. To change this:

```python
# In backend/main.py
storage = Storage(data_dir="your/custom/path")
```

### AI Service Configuration

#### Option 1: No AI (Default)
```python
ai_service = get_ai_service(provider="noop")
```

#### Option 2: Local LLM (Ollama/LM Studio)
First, start your local LLM server on port 8001.

```python
ai_service = get_ai_service(
    provider="local",
    local_server_url="http://localhost:8001"
)
```

#### Option 3: OpenAI
```python
import os
api_key = os.environ.get("OPENAI_API_KEY")
ai_service = get_ai_service(
    provider="openai",
    api_key=api_key
)
```

Set your API key:
```bash
# Linux/Mac
export OPENAI_API_KEY="your-key-here"

# Windows PowerShell
$env:OPENAI_API_KEY="your-key-here"

# Windows CMD
set OPENAI_API_KEY=your-key-here
```

### Backend Host & Port

To change the backend server address, edit `run_backend.py`:

```python
subprocess.run([
    sys.executable, "-m", "uvicorn",
    "main:app",
    "--host", "0.0.0.0",  # Change to 127.0.0.1 for localhost only
    "--port", "8000",     # Change to different port
    "--reload"
])
```

## Frontend Configuration

### Backend URL

To connect to a backend on a different host/port, edit `frontend/main.py`:

```python
def __init__(self):
    super().__init__()
    # ...
    self.client = BudgetAppClient(base_url="http://your-backend-url:8000")
```

Or in `frontend/api_client.py`:

```python
def __init__(self, base_url: str = "http://your-backend-url:8000"):
    self.base_url = base_url
```

### Window Size & Position

```python
def __init__(self):
    super().__init__()
    self.setGeometry(100, 100, 1400, 900)  # Change dimensions
```

### UI Customization

Colors, fonts, and styles can be modified using stylesheets:

```python
self.transactions_table.setStyleSheet("""
    QTableWidget {
        background-color: #f5f5f5;
    }
    QHeaderView::section {
        background-color: #333;
        color: white;
    }
""")
```

## Multi-User Setup (Advanced)

To run Budget App for multiple users:

1. **Separate Data Directories**: Each user gets their own `backend/data/` folder
2. **Authentication**: Add JWT tokens to the API (not included by default)
3. **Separate Backend Instances**: Run multiple backend instances on different ports

Example setup:
```bash
# User 1
STORAGE_DIR=backend/data/user1 python -m uvicorn backend.main:app --port 8001

# User 2
STORAGE_DIR=backend/data/user2 python -m uvicorn backend.main:app --port 8002
```

Then connect each frontend to the appropriate backend:
```python
# User 1 frontend
BudgetAppClient(base_url="http://localhost:8001")

# User 2 frontend
BudgetAppClient(base_url="http://localhost:8002")
```

## Performance Tuning

### Large Dataset Performance

If you have thousands of transactions:

1. **Pagination**: The API already supports pagination with `skip` and `limit`
2. **Indexes**: Consider migrating to a real database (PostgreSQL, SQLite)
3. **Caching**: Add Redis for frequently accessed data

### Memory Usage

```python
# In api_client.py, limit concurrent requests
self.client = httpx.AsyncClient(
    base_url=base_url,
    limits=httpx.Limits(max_connections=10)
)
```

## Backup & Export

### Manual Backup

Simply copy the `backend/data/` folder:
```bash
cp -r backend/data backend/data.backup
```

### Automated Backup (Script)

```bash
# Linux/Mac
0 2 * * * cp -r /path/to/BudgetApp/backend/data /path/to/backups/data-$(date +%Y%m%d)

# Windows Task Scheduler
# Create a batch file that runs:
# xcopy C:\...\BudgetApp\backend\data C:\backups\data-%date% /E /I
```

### Export to Excel/CSV

Add this endpoint to `backend/main.py`:

```python
@app.get("/export/transactions.csv")
async def export_transactions():
    transactions = storage.get_transactions()
    # Convert to CSV and return
```

## Docker Deployment (Optional)

To containerize the app:

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY backend/requirements.txt .
RUN pip install -r requirements.txt

COPY backend /app/backend
EXPOSE 8000

CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Build and run:
```bash
docker build -t budget-app .
docker run -p 8000:8000 -v $(pwd)/backend/data:/app/backend/data budget-app
```

## Security Checklist

- [ ] Change backend host from `0.0.0.0` to `127.0.0.1` for local-only use
- [ ] Add authentication if exposing over network
- [ ] Enable HTTPS/TLS for remote connections
- [ ] Regularly backup `backend/data/` folder
- [ ] Never commit sensitive data (API keys, etc.) to git
- [ ] Use environment variables for configuration

---

For more info, see [README.md](README.md)
