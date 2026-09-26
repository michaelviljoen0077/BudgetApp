# Budget App

A personal expense tracker with a hierarchical category tree, budgets, bank-statement import and
optional AI categorization. It has two parts:

- **backend/**: a FastAPI service that stores everything in JSON files under `backend/data/`
- **frontend/**: a PySide6 desktop app that talks to the backend over HTTP

Amounts are in South African Rand (ZAR).

## Getting started

Requires Python 3.9+.

```bash
python install.py      # installs backend + frontend requirements
python run_app.py      # starts the backend, then opens the desktop app
```

On Windows you can double-click `run_app.bat` instead (it runs the installer the first time).

To run the pieces separately: `python run_backend.py` (API on http://localhost:8000, interactive
docs at http://localhost:8000/docs) and `python run_frontend.py`.

## Using the app

| Tab | What it's for |
| --- | --- |
| Dashboard | Spending by category, spending over time, budget vs. spend, income |
| Transactions | Everything in the ledger; edit or delete rows |
| Budgets | Monthly / quarterly / yearly limits on any category, with progress |
| Unknowns | Uncategorized transactions. Categorizing one also files other unknowns with the same description |
| Possible Duplicates | Transactions sharing a date and amount. **Keep** hides the pair for good, **Delete** removes one |
| Merchants | Description → category rules the app has learned |
| Import | Import a bank statement CSV |

The category tree on the left supports drag-and-drop (to re-parent) and right-click (to delete).
Use the date range and category checkboxes above the tabs to filter every view.

**Budgets.** With no date filter, each budget shows spending for its current period (this month,
quarter or year). With a date filter, the budget is pro-rated to the selected range, e.g. a
R3,000/month budget viewed over 10 days is R986. A subcategory budget can't exceed its parent's.

**Learning.** Whenever you set a transaction's category, the app remembers that description →
category mapping. Future smart entries and CSV imports with the same description use it before
asking the AI.

**CSV import.** Most bank exports work as-is. Metadata lines above the header are skipped, and
either a signed `Amount` column or separate `Debit`/`Credit` columns are understood. Rows already
in the ledger are skipped, so re-importing an overlapping statement is safe.

## AI categorization (optional)

AI suggestions come from a local [Ollama](https://ollama.com) server. Nothing is sent to the
internet. Without Ollama everything still works; new transactions just stay uncategorized until
you file them.

```bash
ollama pull mistral
ollama serve
```

The backend reads these environment variables:

| Variable | Default | |
| --- | --- | --- |
| `BUDGETAPP_AI_PROVIDER` | `local` | `local` (Ollama) or `noop` (disable AI) |
| `OLLAMA_URL` | `http://localhost:11434` | |
| `OLLAMA_MODEL` | `mistral` | any model you have pulled |
| `OLLAMA_TIMEOUT` | `120` | seconds per request |

## Your data

All data lives in `backend/data/` as plain JSON: `ledger.json` (transactions), `categories.json`,
`budgets.json`, `merchants.json` and `ignored_duplicates.json`. Writes are atomic, so a crash can't
leave a half-written file. To back up, copy the folder. To start fresh, delete it, and default
categories are recreated on the next start.

The folder is git-ignored so personal financial data doesn't end up in the repository. The API has
no authentication and only listens on `127.0.0.1`.

## Development

```bash
pip install -r backend/requirements.txt pytest
pytest
```

The tests (`tests/`) exercise the API against a temporary data directory with AI disabled or faked.

| File | Contents |
| --- | --- |
| `backend/main.py` | API routes, budget/period maths, CSV parsing, duplicate detection |
| `backend/storage.py` | JSON file storage |
| `backend/ai_service.py` | Ollama client and categorization prompt |
| `backend/models.py` | Request models |
| `frontend/main.py` | Desktop UI |
| `frontend/api_client.py` | HTTP client for the backend |
