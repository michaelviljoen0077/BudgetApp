# ⚡ Quick Start Guide

Get the Budget App up and running in 5 minutes!

## Prerequisites

- Python 3.8 or higher
- pip (Python package manager)

Check your Python version:
```bash
python --version
```

## Installation

### Step 1: One-Time Setup

Run the setup script to install all dependencies:

```bash
python setup.py
```

This will:
- Install FastAPI, Uvicorn, and backend dependencies
- Install PySide6 and frontend dependencies
- Create the `backend/data/` directory for JSON files

### Step 2: Start the Backend

In your first terminal window:

```bash
python run_backend.py
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

The backend is now ready! You can access:
- **API Explorer**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

### Step 3: Start the Frontend

In a **new terminal window**, run:

```bash
python run_frontend.py
```

The desktop application window will open. You're ready to go!

## First Steps

1. **Create a Transaction**
   - Click "New Transaction"
   - Fill in date, amount, description, and merchant
   - Select a category or leave blank
   - Click OK

2. **Create a Budget**
   - Click "New Budget"
   - Pick a category (e.g., "Food & Dining")
   - Set amount (e.g., $500)
   - Choose period (Monthly)
   - Click OK

3. **Import Bank Statement**
   - Click "Import" tab
   - Click "Import Bank CSV"
   - Select a CSV file from your bank
   - Transactions will be added to "Unknowns" tab

4. **Categorize Unknowns**
   - Go to "Unknowns" tab
   - Click "Categorize" on a transaction
   - Assign it to a category
   - Click OK

5. **View Budgets**
   - Go to "Budgets" tab
   - See progress bars for each budget
   - Green = OK, Yellow = Approaching, Red = Exceeded

## Example CSV Format

If importing from your bank, ensure the CSV has these columns:
```
Date,Description,Amount
2024-01-15,Starbucks,-5.50
2024-01-16,Target,-42.30
2024-01-17,Salary,3000.00
```

You can customize this in [CONFIGURATION.md](CONFIGURATION.md).

## Troubleshooting

### "Connection refused" when opening frontend?
- Backend isn't running. Start it first with `python run_backend.py`

### "Module not found" errors?
- Run `python setup.py` again to ensure dependencies are installed

### Data isn't persisting?
- Check that `backend/data/` directory exists and is writable
- Look for error messages in the backend terminal

### Can't install PySide6?
- PySide6 requires build tools. On Windows, install Visual Studio C++ Build Tools
- On Mac, you may need Xcode command line tools: `xcode-select --install`
- On Linux, install Qt development packages: `sudo apt install libqt6core6`

## File Structure

After setup, your directory should look like:

```
BudgetApp/
├── backend/
│   ├── data/
│   │   ├── ledger.json         (transactions)
│   │   ├── categories.json     (category tree)
│   │   ├── budgets.json        (budget definitions)
│   │   └── merchants.json      (merchant rules)
│   ├── main.py                 (API server)
│   ├── models.py               (data models)
│   ├── storage.py              (JSON storage)
│   ├── ai_service.py           (AI integration)
│   └── requirements.txt
├── frontend/
│   ├── main.py                 (desktop UI)
│   ├── api_client.py           (API client)
│   └── requirements.txt
├── run_backend.py
├── run_frontend.py
├── setup.py
├── README.md
└── CONFIGURATION.md
```

## Default Categories

The app comes with these default categories:
- 🍔 **Food & Dining** (Groceries, Restaurants, Takeout)
- 🚗 **Transportation** (Gas, Parking, Public Transit)
- ⚡ **Utilities** (Electricity, Water, Internet)
- 🎬 **Entertainment** (Movies, Games, Hobbies)
- 💪 **Health & Fitness** (Gym, Medical, Medications)
- 🛍️ **Shopping** (Clothing, Electronics, Books)
- 💰 **Income** (Salary, Freelance, Investments)

Add more with "New Category" button.

## Next Steps

- 📖 Read [README.md](README.md) for detailed feature documentation
- ⚙️ Check [CONFIGURATION.md](CONFIGURATION.md) for customization options
- 📊 Explore the API at http://localhost:8000/docs
- 💡 Build a mobile app using the same backend API!

## Common Tasks

### Reset All Data

To start fresh, delete the data files:

```bash
rm backend/data/*.json
```

Restart the backend and it will recreate files with defaults.

### Change Backend Port

Edit `run_backend.py`:
```python
"--port", "8000",  # Change to 9000, etc.
```

Then update frontend to connect to new port:
Edit `frontend/main.py`:
```python
self.client = BudgetAppClient(base_url="http://localhost:9000")
```

### Export Your Data

Your data is already in simple JSON format! You can:
- Open `backend/data/ledger.json` in any text editor
- Convert to Excel/CSV using any tool
- Backup by copying the `backend/data/` folder

---

**Happy budgeting! 🎯💰**

Need help? Check the [README.md](README.md) or [CONFIGURATION.md](CONFIGURATION.md).
