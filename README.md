# 🧾 Budget App – Tree-Based Budgeting & Expense Tracker

A personal expense tracker and budgeting system with a real backend (FastAPI) and a beautiful desktop client (PySide6). Uses structured JSON files for storage.

## 📋 Overview

**Budget App** is a desktop-first application for managing your finances with a tree-based category system. Key features:

- ✨ **Hierarchical Category Tree** – Organize expenses (e.g., Food → Takeouts → McDonald's)
- 💾 **JSON-based Storage** – All data in plain JSON files (ledger.json, categories.json, budgets.json, merchants.json)
- 🔌 **Real Backend API** – FastAPI service running locally, exposable to multiple frontends
- 📊 **Budget Tracking** – Define budgets on any category node and get real-time status
- 📥 **Bank Statement Import** – Upload CSV files to auto-categorize transactions
- 🤖 **AI Integration** – Pluggable AI service for smart categorization (noop/local/remote)
- 🔄 **Reconciliation** – Match receipts against bank statements to avoid double-counting
- 💻 **Desktop UI** – Rich PySide6 interface with transaction table, budget view, unknowns page

## 🏗️ Project Structure

```
BudgetApp/
├── backend/
│   ├── main.py              # FastAPI app with all endpoints
│   ├── models.py            # Pydantic models for domain entities
│   ├── storage.py           # JSON file storage layer
│   ├── ai_service.py        # Pluggable AI service interface
│   ├── requirements.txt      # Backend dependencies
│   └── data/                # JSON data files (auto-created)
│       ├── ledger.json
│       ├── categories.json
│       ├── budgets.json
│       └── merchants.json
├── frontend/
│   ├── main.py              # PySide6 desktop UI
│   ├── api_client.py        # HTTP client for backend API
│   └── requirements.txt      # Frontend dependencies
├── run_backend.py           # Script to start the backend
├── run_frontend.py          # Script to start the frontend
└── README.md                # This file
```

## 🚀 Quick Start

### 1. Install Dependencies

**Backend:**
```bash
cd backend
pip install -r requirements.txt
```

**Frontend:**
```bash
cd frontend
pip install -r requirements.txt
```

Or install all at once from the root directory:
```bash
pip install -r backend/requirements.txt -r frontend/requirements.txt
```

### 2. Start the Backend

```bash
python run_backend.py
```

The backend will start on `http://localhost:8000`. You can access:
- **API Documentation**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### 3. Start the Frontend

In a **new terminal window**, run:
```bash
python run_frontend.py
```

The desktop application will launch. It will automatically connect to the backend at `http://localhost:8000`.

## 🎯 Features & Usage

### Transactions
- **View Transactions**: See all transactions in the main "Transactions" tab, sorted by date
- **Create Transaction**: Click "New Transaction" to add an expense/income
- **Update Category**: Click "Categorize" on unknown transactions to assign them to a category
- **Delete**: Remove unwanted transactions
- **Filter**: Use query parameters in the API (date range, category, merchant, tags)

### Categories
- **Hierarchical Tree**: Left panel shows a tree of all categories with icons
- **Default Categories**: App ships with common categories (Food, Transportation, Utilities, etc.)
- **Create Category**: Click "New Category" to add a custom category under any parent
- **Drag & Drop**: (Future) Recategorize transactions via drag-and-drop

### Budgets
- **Define Budgets**: Click "New Budget" to set spending limits on any category
- **Budget Status**: "Budgets" tab shows progress bars and status (OK/APPROACHING/EXCEEDED)
- **Warnings**: Color-coded progress bars (green → yellow → red as you approach/exceed limits)
- **Period**: Monthly, quarterly, or yearly budgets

### Bank Statement Import
- **Import CSV**: Click "Import Bank CSV" in the "Import" tab
- **Supported Formats**: Generic CSV (easily extendable for Chase, BofA, etc.)
- **Auto-tagging**: Imported transactions are tagged with "imported"
- **Categorization**: Use the "Unknowns" tab to categorize them

### Unknowns Page
- **View Uncategorized**: "Unknowns" tab shows all transactions without categories
- **Quick Categorize**: Click "Categorize" to assign category and merchant
- **Batch Operations**: (Future) AI-powered bulk categorization

### Reconciliation
- **Match Bank Statements & Receipts**: Backend correlates by amount/date/merchant
- **Confirm Matches**: UI to verify or override matches
- **Avoid Double-Counting**: Prevents the same expense from being counted twice

## 📡 API Endpoints

All endpoints are RESTful JSON APIs. Examples:

### Transactions
- `GET /transactions` – List transactions (with filters: from_date, to_date, category_path, merchant, tags)
- `POST /transactions` – Create transaction
- `PATCH /transactions/{id}` – Update transaction
- `DELETE /transactions/{id}` – Delete transaction
- `GET /transactions/unknown` – List uncategorized transactions

### Categories
- `GET /categories` – Get entire category tree
- `POST /categories` – Create category
- `PUT /categories` – Replace entire tree

### Budgets
- `GET /budgets` – List budgets
- `POST /budgets` – Create budget
- `GET /budgets/{id}` – Get specific budget
- `DELETE /budgets/{id}` – Delete budget
- `GET /budgets/status` – Get budget status with spending

### Merchants
- `GET /merchants` – List merchants
- `POST /merchants` – Create merchant
- `PATCH /merchants/{id}` – Update merchant
- `DELETE /merchants/{id}` – Delete merchant

### Imports
- `POST /imports/bank-csv` – Import bank CSV

### Reconciliation
- `GET /reconciliation` – Get reconciliation candidates

### AI
- `POST /ai/categorise` – AI-powered categorization
- `POST /ai/enrich-merchant` – Enrich merchant data

## 💾 Data Storage

All data is stored in JSON files in the `backend/data/` directory:

- **ledger.json** – All transactions
- **categories.json** – Category tree structure
- **budgets.json** – Budget definitions
- **merchants.json** – Merchant dictionary for categorization

Files are written atomically (write to temp, then rename) to prevent corruption.

## 🤖 AI Integration

The backend includes a pluggable AI service for smart categorization:

```python
# In ai_service.py
ai_service = get_ai_service(provider="noop")  # Options: "noop", "local", "openai", "anthropic"
```

### Options:
1. **No-op** (default) – No AI enrichment
2. **Local LLM** – Ollama/LM Studio on localhost:8001
3. **Remote APIs** – OpenAI, Anthropic, Google (requires API key)

Extend `AiServiceBase` to add custom providers.

## 🛠️ Extending the App

### Add a New Frontend
Since all business logic lives in the backend, you can build:
- Web SPA (React, Vue, Svelte)
- Mobile app (Flutter, React Native)
- CLI tool
- Another desktop framework

Just call the same HTTP API endpoints!

### Customize Bank Format Parsing
Edit `backend/main.py` in the `import_bank_csv` endpoint to handle your bank's CSV format:

```python
# Map your bank's column names
date_str = row.get("Transaction Date")
amount_str = row.get("Amount")
description = row.get("Description")
```

### Add More Categories
Edit the default categories in `backend/main.py` in the `init_categories` startup event.

### Implement Real AI
Edit `backend/ai_service.py` to call actual LLM APIs:

```python
# Example: OpenAI integration
async def categorise_transactions(self, transactions, categories):
    # Call OpenAI API
    # Return enriched transactions
    pass
```

## 🔐 Security Notes

- **Local-First**: Data never leaves your machine by default
- **API Security**: Currently no authentication (designed for local use)
- **Data Privacy**: All transactions stored in plain JSON files you control
- **To Add Auth**: Implement JWT or OAuth2 in FastAPI

## 📦 Dependencies

**Backend:**
- FastAPI – Web framework
- Uvicorn – ASGI server
- Pydantic – Data validation
- python-dateutil – Date parsing

**Frontend:**
- PySide6 – Qt for Python UI
- httpx – Async HTTP client

## 🐛 Troubleshooting

### "Cannot connect to backend"
- Make sure backend is running: `python run_backend.py`
- Check if it's on http://localhost:8000/health

### "Import failed"
- Ensure CSV format matches expected columns (Date, Description, Amount)
- Check date format (should be parseable by dateutil)

### "Permission denied" on JSON files
- Check `backend/data/` folder permissions
- Ensure the directory exists and is writable

## 📝 Future Ideas

- [ ] Web UI (React/Vue)
- [ ] Mobile app (Flutter)
- [ ] Receipt image OCR + categorization
- [ ] Export to PDF/Excel reports
- [ ] Real-time notifications for budget warnings
- [ ] Tags-based filtering and budgeting
- [ ] Multi-user support (with auth)
- [ ] Database backend (PostgreSQL) as alternative to JSON
- [ ] Investment tracking & portfolio analysis
- [ ] Tax categorization helper

## 📄 License

MIT License – Feel free to use, modify, and extend!

## 🤝 Contributing

To extend or improve:
1. Fork/clone the repository
2. Create a feature branch
3. Make your changes
4. Test with both backend and frontend
5. Submit a pull request

## 📧 Support

For issues or questions, check:
- FastAPI docs at http://localhost:8000/docs
- Python documentation
- GitHub issues

---

**Happy budgeting!** 🎯💰
