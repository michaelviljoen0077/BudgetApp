# 🛠️ Developer Guide – Extending Budget App

Guide for developers who want to extend or customize the Budget App.

## Architecture Overview

The app follows a **clean separation of concerns**:

```
Frontend (PySide6)
    ↓ (HTTP REST API)
Backend (FastAPI)
    ↓ (File I/O)
Storage (JSON files)
```

This allows:
- Frontend to be swapped (web, mobile, CLI)
- Multiple frontends using same backend
- Easy testing and debugging

## Adding a New API Endpoint

### Example: Add a "Summary" Endpoint

1. **Define the Pydantic model** in `backend/models.py`:

```python
class SummaryResponse(BaseModel):
    total_spent: Decimal
    total_income: Decimal
    net: Decimal
    budget_count: int
    transaction_count: int
```

2. **Add the endpoint** in `backend/main.py`:

```python
@app.get("/summary")
async def get_summary():
    """Get spending summary."""
    transactions = storage.get_transactions()
    budgets = storage.get_budgets()
    
    total_spent = sum(
        Decimal(str(t.get("amount", 0)))
        for t in transactions
        if t.get("transaction_type") == "expense"
    )
    
    total_income = sum(
        Decimal(str(t.get("amount", 0)))
        for t in transactions
        if t.get("transaction_type") == "income"
    )
    
    return {
        "total_spent": float(total_spent),
        "total_income": float(total_income),
        "net": float(total_income - total_spent),
        "budget_count": len(budgets),
        "transaction_count": len(transactions)
    }
```

3. **Add to frontend client** in `frontend/api_client.py`:

```python
async def get_summary(self) -> Dict[str, Any]:
    """Get spending summary."""
    response = await self.client.get("/summary")
    response.raise_for_status()
    return response.json()
```

4. **Use in frontend UI**:

```python
async def _load_summary(self):
    try:
        summary = await self.client.get_summary()
        self.summary_label.setText(
            f"Total: ${summary['total_spent']:.2f} | "
            f"Net: ${summary['net']:.2f}"
        )
    except Exception as e:
        self.show_error(f"Failed to load summary: {e}")
```

## Adding a New UI Tab

### Example: Add a "Reports" Tab

1. **Create the UI component** in `frontend/main.py`:

```python
def init_ui(self):
    # ... existing code ...
    
    # Add to tabs
    self.reports_widget = QWidget()
    self.reports_layout = QVBoxLayout()
    
    self.reports_button = QPushButton("Generate Report")
    self.reports_button.clicked.connect(self.generate_report)
    self.reports_layout.addWidget(self.reports_button)
    
    self.reports_widget.setLayout(self.reports_layout)
    tabs.addTab(self.reports_widget, "Reports")
```

2. **Implement the logic**:

```python
def generate_report(self):
    """Generate a spending report."""
    asyncio.create_task(self._generate_report())

async def _generate_report(self):
    """Async generate report."""
    try:
        # Call backend endpoint
        report = await self.client.get_report()
        
        # Display results
        self.show_info(f"Report generated: {report}")
    except Exception as e:
        self.show_error(f"Failed to generate report: {e}")
```

## Implementing AI Integration

The app has a pluggable AI service. To implement OpenAI integration:

1. **Create OpenAI implementation** in `backend/ai_service.py`:

```python
import openai

class OpenAiService(AiServiceBase):
    def __init__(self, api_key: str, model: str = "gpt-3.5-turbo"):
        self.api_key = api_key
        self.model = model
        openai.api_key = api_key

    async def categorise_transactions(
        self,
        transactions: List[Dict],
        categories: Dict[str, Any]
    ) -> List[Dict]:
        """Use OpenAI to suggest categories."""
        
        # Build category list for context
        category_names = [
            node["name"] for node in categories.get("nodes", {}).values()
        ]
        
        for trans in transactions:
            if trans.get("category_path"):
                continue
            
            prompt = f"""
            Given this transaction, pick the best category from the list.
            
            Categories: {', '.join(category_names)}
            
            Transaction: {trans.get('description')} (${trans.get('amount')})
            Merchant: {trans.get('merchant')}
            
            Respond with ONLY the category name.
            """
            
            try:
                response = openai.ChatCompletion.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3
                )
                
                category = response.choices[0].message.content.strip()
                trans["category_path"] = category
            except Exception as e:
                print(f"OpenAI error: {e}")
        
        return transactions

    async def enrich_merchant(
        self,
        merchant_name: str,
        description: str
    ) -> Dict[str, Any]:
        """Enrich merchant with OpenAI."""
        
        prompt = f"""
        Given this merchant, suggest:
        1. Aliases (variations of the name)
        2. Default category
        
        Merchant: {merchant_name}
        Description: {description}
        
        Respond in JSON format:
        {{"aliases": [...], "suggested_category": "..."}}
        """
        
        try:
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            
            import json
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            print(f"OpenAI error: {e}")
            return {"aliases": [], "suggested_category": None}
```

2. **Use it in main.py**:

```python
import os

# Initialize AI service
ai_provider = os.environ.get("AI_PROVIDER", "noop")
ai_service = get_ai_service(provider=ai_provider)
```

3. **Set environment variable**:

```bash
export OPENAI_API_KEY="sk-..."
export AI_PROVIDER="openai"
python run_backend.py
```

## Adding CSV Bank Format Support

To support a specific bank format, extend the CSV parser:

```python
@app.post("/imports/bank-csv")
async def import_bank_csv(req: BankImportRequest):
    """Import transactions from bank CSV."""
    
    if req.bank_format == "chase":
        return await import_chase_csv(req.file_content)
    elif req.bank_format == "bofa":
        return await import_bofa_csv(req.file_content)
    else:
        return await import_generic_csv(req.file_content)

async def import_chase_csv(csv_content: str):
    """Chase-specific CSV parsing."""
    csv_reader = csv.DictReader(io.StringIO(csv_content))
    
    for row in csv_reader:
        date_str = row.get("Transaction Date")
        description = row.get("Description")
        # Chase uses separate debit/credit columns
        debit = float(row.get("Debit", 0) or 0)
        credit = float(row.get("Credit", 0) or 0)
        amount = debit if debit > 0 else credit
        
        # Create transaction...
```

## Testing the API

Use the built-in API documentation at http://localhost:8000/docs or use curl:

```bash
# Create a transaction
curl -X POST http://localhost:8000/transactions \
  -H "Content-Type: application/json" \
  -d '{
    "date": "2024-01-15T00:00:00",
    "description": "Test",
    "amount": 50.00
  }'

# List transactions
curl http://localhost:8000/transactions

# Get a category
curl http://localhost:8000/categories
```

## Database Migration (Advanced)

To migrate from JSON to a real database:

1. **Add SQLAlchemy** to `backend/requirements.txt`:
```
sqlalchemy==2.0.0
```

2. **Create models** in `backend/db_models.py`:
```python
from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(String, primary_key=True)
    date = Column(DateTime)
    description = Column(String)
    amount = Column(Float)
    # ...
```

3. **Create a DB storage class** in `backend/db_storage.py`:
```python
class DbStorage(Storage):
    def __init__(self, db_url: str):
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)
    
    def get_transactions(self):
        return self.session.query(Transaction).all()
    # ...
```

4. **Use it in main.py**:
```python
# storage = Storage(data_dir="backend/data")
storage = DbStorage(db_url="postgresql://user:pass@localhost/budgetapp")
```

## Debugging

### Enable verbose logging:

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@app.get("/debug")
async def debug():
    logger.debug("Debug message")
    return {"status": "debug"}
```

### Inspect JSON files:

```bash
cat backend/data/ledger.json | python -m json.tool
```

### Frontend debugging:

Add print statements or use Qt's built-in debugger:
```python
print(f"Debug: {variable}")  # Simple debugging
```

## Performance Optimization

### Cache frequently accessed data:

```python
from functools import lru_cache

@lru_cache(maxsize=128)
def get_category_by_id(category_id: str):
    categories = storage.get_categories()
    return categories.get("nodes", {}).get(category_id)
```

### Lazy-load data:

```python
async def load_transactions_lazy(self):
    """Load transactions in chunks."""
    for i in range(0, 10000, 100):
        data = await self.client.list_transactions(skip=i, limit=100)
        # Process and display batch
        yield data
```

## Security Best Practices

1. **Add authentication**:
```python
from fastapi.security import HTTPBearer

security = HTTPBearer()

@app.get("/protected")
async def protected(credentials: HTTPAuthenticationCredentials = Depends(security)):
    # Verify token
    pass
```

2. **Validate user input**:
```python
from pydantic import validator

class CreateTransactionRequest(BaseModel):
    amount: Decimal = Field(gt=0)  # Must be positive
    description: str = Field(min_length=1, max_length=255)
```

3. **Rate limiting**:
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/transactions", _rate_limit_="10/minute")
async def create_transaction(req: CreateTransactionRequest):
    pass
```

## Contribution Workflow

1. Fork/clone the repo
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make changes
4. Test with both backend and frontend
5. Commit: `git commit -am 'Add feature'`
6. Push: `git push origin feature/my-feature`
7. Create pull request

## Resources

- FastAPI docs: https://fastapi.tiangolo.com
- Pydantic docs: https://docs.pydantic.dev
- PySide6 docs: https://doc.qt.io/qtforpython
- Python async: https://docs.python.org/3/library/asyncio.html

---

Happy developing! 🚀
