"""
FastAPI backend for the Budget App.
Exposes a REST API for transactions, categories, budgets, merchants, imports and duplicates.
"""
import csv
import io
import logging
from collections import Counter, defaultdict
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Dict, Iterable, List, Optional, Tuple

from dateutil import parser as date_parser
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from ai_service import AiUnavailableError, extract_json, get_ai_service
from models import (
    DEFAULT_CURRENCY, BankImportRequest, BudgetPeriod, BudgetStatus, CategoryTree,
    CreateBudgetRequest, CreateCategoryRequest, CreateMerchantRequest, CreateTransactionRequest,
    IgnoreDuplicatesRequest, SmartTransactionRequest, TransactionType, UpdateBudgetRequest,
    UpdateCategoryRequest, UpdateMerchantRequest, UpdateTransactionRequest,
)
from storage import NotFoundError, Storage

logger = logging.getLogger("budgetapp")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)

storage = Storage()
ai_service = get_ai_service()

UNKNOWN_CATEGORY_MARKERS = ("Unidentified", "Other Expenses")
PERIOD_DAYS = {BudgetPeriod.MONTHLY: 365.25 / 12, BudgetPeriod.QUARTERLY: 365.25 / 4, BudgetPeriod.YEARLY: 365.25}

DEFAULT_CATEGORIES = [
    ("Food & Dining", "🍔", "#FF6B6B", [("Groceries", "🥬"), ("Restaurants", "🍽️"), ("Takeout", "🍜")]),
    ("Transportation", "🚗", "#4ECDC4", [("Petrol", "⛽"), ("Parking", "🅿️"), ("Public Transit", "🚌")]),
    ("Utilities", "⚡", "#95E1D3", [("Electricity", "💡"), ("Water", "💧"), ("Internet", "📡")]),
    ("Entertainment", "🎬", "#F38181", [("Movies", "🎥"), ("Games", "🎮"), ("Hobbies", "🎨")]),
    ("Health & Fitness", "💪", "#AA96DA", [("Gym", "🏋️"), ("Medical", "⚕️"), ("Medications", "💊")]),
    ("Shopping", "🛍️", "#FCBAD3", [("Clothing", "👕"), ("Electronics", "📱"), ("Books", "📚")]),
    ("Income", "💰", "#A8E6CF", [("Salary", "💼"), ("Freelance", "💻"), ("Investments", "📈")]),
]


def seed_default_categories():
    """Create the default category tree if no categories exist yet."""
    if storage.get_categories().get("nodes"):
        return

    def slug(name):
        return name.lower().replace(" ", "_")

    tree = {"nodes": {}, "root_ids": []}
    for name, icon, color, children in DEFAULT_CATEGORIES:
        root_id = slug(name)
        tree["root_ids"].append(root_id)
        tree["nodes"][root_id] = {
            "id": root_id, "name": name, "parent_id": None, "icon": icon, "color": color,
            "children": [slug(child) for child, _ in children],
        }
        for child, child_icon in children:
            tree["nodes"][slug(child)] = {
                "id": slug(child), "name": child, "parent_id": root_id, "icon": child_icon,
                "color": None, "children": [],
            }
    storage.update_categories(tree)
    logger.info("Created default categories")


@asynccontextmanager
async def lifespan(app: FastAPI):
    seed_default_categories()
    yield


app = FastAPI(
    title="Budget App Backend",
    description="Personal expense tracker with tree-based budgeting",
    version="1.1.0",
    lifespan=lifespan,
)

# The desktop client talks to the API directly; CORS only matters for browser clients.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ============ HELPERS ============

def parse_date(value: Optional[str]) -> Optional[date]:
    """Parse a stored or query date ('2025-12-14' or full ISO timestamp) to a date."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def parse_query_date(value: Optional[str], name: str) -> Optional[date]:
    parsed = parse_date(value)
    if value and parsed is None:
        raise HTTPException(status_code=422, detail=f"Invalid {name}: {value!r} (expected YYYY-MM-DD)")
    return parsed


def category_paths(tree: Dict) -> List[str]:
    """All category paths in the tree, e.g. ['Food & Dining', 'Food & Dining/Groceries', ...]."""
    nodes = tree.get("nodes", {})
    paths = []

    def walk(node_id, prefix, seen):
        node = nodes.get(node_id)
        if not node or node_id in seen:
            return
        path = f"{prefix}/{node['name']}" if prefix else node["name"]
        paths.append(path)
        for child_id in node.get("children", []):
            walk(child_id, path, seen | {node_id})

    for node_id, node in nodes.items():
        if not node.get("parent_id") or node["parent_id"] not in nodes:
            walk(node_id, "", frozenset())
    return paths


def node_path(nodes: Dict, node_id: str) -> str:
    """Full path of a single category node."""
    parts, seen = [], set()
    while node_id in nodes and node_id not in seen:
        seen.add(node_id)
        parts.append(nodes[node_id]["name"])
        node_id = nodes[node_id].get("parent_id")
    return "/".join(reversed(parts))


def path_matches(transaction_path: Optional[str], category: str) -> bool:
    """
    True if a transaction's category path falls under `category`.
    `category` may be a full path ("Food & Dining/Groceries") or a bare
    category name ("Groceries"), which matches that name at any level.
    Matching is on whole path segments, so "Food" does not match "Food & Dining".
    """
    if not transaction_path or not category:
        return False
    return f"/{category}/" in f"/{transaction_path}/"


def is_expense(transaction: Dict) -> bool:
    return transaction.get("transaction_type") == TransactionType.EXPENSE.value


def in_range(transaction: Dict, start: Optional[date], end: Optional[date]) -> bool:
    tx_date = parse_date(transaction.get("date"))
    if tx_date is None:
        return False
    return (start is None or tx_date >= start) and (end is None or tx_date <= end)


def current_period_window(period: str, today: date) -> Tuple[date, date]:
    """First and last day of the calendar month/quarter/year containing `today`."""
    if period == BudgetPeriod.YEARLY:
        return date(today.year, 1, 1), date(today.year, 12, 31)
    if period == BudgetPeriod.QUARTERLY:
        first_month = 3 * ((today.month - 1) // 3) + 1
        start = date(today.year, first_month, 1)
        months = 3
    else:
        start = date(today.year, today.month, 1)
        months = 1
    next_month = start.month - 1 + months
    end = date(start.year + next_month // 12, next_month % 12 + 1, 1) - timedelta(days=1)
    return start, end


def serialize(values: Dict) -> Dict:
    """Convert pydantic output (Decimals, datetimes, enums) into JSON-storable values."""
    out = {}
    for key, value in values.items():
        if isinstance(value, Decimal):
            value = float(value)
        elif isinstance(value, datetime):
            value = value.isoformat()
        elif isinstance(value, Enum):
            value = value.value
        out[key] = value
    return out


def not_found(error: NotFoundError):
    return HTTPException(status_code=404, detail=str(error))


# ============ HEALTH ============

@app.get("/health")
async def health():
    return {"status": "ok"}


# ============ TRANSACTIONS ============

def paginate(items: List[Dict], skip: int, limit: int) -> Dict:
    return {"total": len(items), "skip": skip, "limit": limit, "transactions": items[skip:skip + limit]}


@app.get("/transactions")
async def list_transactions(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    category_path: Optional[str] = None,
    merchant: Optional[str] = None,
    tags: Optional[str] = Query(None, description="comma-separated"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1),
):
    """List transactions (newest first) with optional filters."""
    start = parse_query_date(from_date, "from_date")
    end = parse_query_date(to_date, "to_date")
    transactions = storage.get_transactions()

    if start or end:
        transactions = [t for t in transactions if in_range(t, start, end)]
    if category_path:
        transactions = [t for t in transactions if path_matches(t.get("category_path"), category_path)]
    if merchant:
        transactions = [t for t in transactions if (t.get("merchant") or "").lower() == merchant.lower()]
    if tags:
        wanted = {tag.strip() for tag in tags.split(",")}
        transactions = [t for t in transactions if wanted & set(t.get("tags", []))]

    transactions.sort(key=lambda t: t.get("date", ""), reverse=True)
    return paginate(transactions, skip, limit)


@app.get("/transactions/unknown")
async def get_unknown_transactions(skip: int = Query(0, ge=0), limit: int = Query(100, ge=1)):
    """Transactions with no category, or filed under an 'Unidentified'/'Other Expenses' bucket."""
    unknown = [
        t for t in storage.get_transactions()
        if not t.get("category_path")
        or any(marker in t["category_path"] for marker in UNKNOWN_CATEGORY_MARKERS)
    ]
    unknown.sort(key=lambda t: t.get("date", ""), reverse=True)
    return paginate(unknown, skip, limit)


@app.get("/transactions/{transaction_id}")
async def get_transaction(transaction_id: str):
    transaction = storage.get_transaction(transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction


@app.post("/transactions")
async def create_transaction(req: CreateTransactionRequest):
    """Create a transaction with all fields supplied."""
    return storage.create_transaction({**serialize(req.model_dump()), "source": "manual"})


@app.post("/transactions/smart")
async def create_smart_transaction(req: SmartTransactionRequest):
    """
    Create an expense from just a description and amount.
    A learned merchant preference wins; otherwise the AI picks (or creates) a category.
    If the AI is unavailable the transaction is still created, uncategorized.
    """
    description = req.description.strip()
    paths = category_paths(storage.get_categories())

    merchant = storage.get_merchant_by_name(description)
    learned = merchant.get("preferred_category") if merchant else None

    category_path = learned if learned in paths else None
    category_created = False
    cleaned_description = description
    ai_note = None

    if category_path is None:
        try:
            suggestion = await _ai_suggest_category(description, req.amount, paths)
        except AiUnavailableError as e:
            logger.warning("Smart entry without AI: %s", e)
            ai_note = f"AI unavailable: {e}"
            suggestion = {}

        suggested = (suggestion.get("suggested_category") or "").strip()
        cleaned_description = (suggestion.get("description") or description).strip() or description
        if suggested in paths:
            category_path = suggested
        elif suggested and "/" not in suggested:
            storage.create_category({
                "name": suggested, "parent_id": None, "icon": "📁", "color": "#4A90E2",
                "description": "Auto-created by AI",
            })
            category_path = suggested
            category_created = True

    if learned and category_path == learned:
        notes = f"Learned category: {learned}"
    elif category_path:
        notes = f"AI categorized: {category_path}"
    else:
        notes = ai_note

    transaction = storage.create_transaction({
        "date": date.today().isoformat(),
        "description": cleaned_description,
        "amount": float(req.amount),
        "currency": DEFAULT_CURRENCY,
        "category_path": category_path,
        "merchant": None,
        "tags": ["smart_entry"],
        "transaction_type": TransactionType.EXPENSE.value,
        "notes": notes,
        "source": "smart_entry",
    })

    return {
        "transaction": transaction,
        "ai_suggestion": category_path,
        "category_created": category_created,
        "message": f"Transaction created and categorized as '{category_path}'!"
        if category_path else "Transaction created (uncategorized).",
    }


async def _ai_suggest_category(description: str, amount: Decimal, paths: List[str]) -> Dict:
    categories_context = (
        "EXISTING CATEGORIES (use these first, avoid duplicates):\n" + "\n".join(f"- {p}" for p in paths)
        if paths else "No categories exist yet."
    )
    prompt = f"""Transaction to parse:
Description: {description}
Amount: {amount}

{categories_context}

If a matching category exists, use it EXACTLY as written. Only suggest a new category name if none of the existing ones are suitable.

Respond with JSON only:
{{"description": "cleaned description", "suggested_category": "exact existing category or new category name"}}"""
    return extract_json(await ai_service.complete(prompt)) or {}


@app.patch("/transactions/{transaction_id}")
async def update_transaction(transaction_id: str, req: UpdateTransactionRequest):
    """Update a transaction. Setting a category teaches the app that description's category."""
    original = storage.get_transaction(transaction_id)
    if not original:
        raise HTTPException(status_code=404, detail="Transaction not found")

    updates = serialize(req.model_dump(exclude_unset=True))
    result = storage.update_transaction(transaction_id, updates)

    if updates.get("category_path"):
        _learn_merchant_category(result.get("description", ""), updates["category_path"])
    return result


def _learn_merchant_category(description: str, category_path: str):
    """Remember that transactions with this description belong in `category_path`."""
    name = description.strip().lower()
    if not name:
        return
    merchant = storage.get_merchant_by_name(name)
    if merchant:
        storage.update_merchant(merchant["id"], {"preferred_category": category_path})
    else:
        storage.create_merchant({
            "name": name, "preferred_category": category_path, "aliases": [name], "confidence": 1.0,
        })
    logger.info("Learned %r -> %r", name, category_path)


@app.delete("/transactions/{transaction_id}")
async def delete_transaction(transaction_id: str):
    try:
        storage.delete_transaction(transaction_id)
    except NotFoundError as e:
        raise not_found(e)
    return {"status": "deleted", "id": transaction_id}


# ============ CATEGORIES ============

@app.get("/categories")
async def get_categories():
    return storage.get_categories()


@app.post("/categories")
async def create_category(req: CreateCategoryRequest):
    """Create a category. `parent_id` may be a category ID or a category name."""
    parent_id = req.parent_id
    if parent_id:
        nodes = storage.get_categories().get("nodes", {})
        if parent_id not in nodes:
            parent_id = next((nid for nid, n in nodes.items() if n["name"] == parent_id), None)
            if parent_id is None:
                raise HTTPException(status_code=404, detail=f"Parent category not found: {req.parent_id}")

    return storage.create_category({**req.model_dump(), "parent_id": parent_id, "children": []})


@app.put("/categories")
async def replace_categories(tree: CategoryTree):
    storage.update_categories(tree.model_dump())
    return storage.get_categories()


@app.patch("/categories/{category_id}")
async def update_category(category_id: str, req: UpdateCategoryRequest):
    """Rename/restyle a category or move it under a new parent (parent_id=null for root)."""
    categories = storage.get_categories()
    nodes = categories.get("nodes", {})
    roots = categories.setdefault("root_ids", [])
    if category_id not in nodes:
        raise HTTPException(status_code=404, detail="Category not found")

    node = nodes[category_id]
    updates = req.model_dump(exclude_unset=True)

    if "parent_id" in updates:
        new_parent_id = updates.pop("parent_id")
        if new_parent_id is not None:
            if new_parent_id not in nodes:
                raise HTTPException(status_code=404, detail="New parent category not found")
            if new_parent_id == category_id or new_parent_id in storage.get_category_descendants(category_id, nodes):
                raise HTTPException(status_code=400, detail="A category cannot be moved inside itself")

        old_parent_id = node.get("parent_id")
        if old_parent_id in nodes:
            nodes[old_parent_id]["children"] = [c for c in nodes[old_parent_id].get("children", []) if c != category_id]
        if category_id in roots:
            roots.remove(category_id)

        if new_parent_id is None:
            roots.append(category_id)
        else:
            nodes[new_parent_id].setdefault("children", []).append(category_id)
        node["parent_id"] = new_parent_id

    node.update(updates)
    storage.update_categories(categories)
    return storage.get_categories()


@app.delete("/categories/{category_id}")
async def delete_category(category_id: str):
    """Delete a category (and its subcategories); their transactions become uncategorized."""
    nodes = storage.get_categories().get("nodes", {})
    if category_id not in nodes:
        raise HTTPException(status_code=404, detail="Category not found")

    doomed = [category_id] + storage.get_category_descendants(category_id, nodes)
    doomed_paths = [node_path(nodes, nid) for nid in doomed]
    doomed_names = {nodes[nid]["name"] for nid in doomed}

    def belongs(path: Optional[str]) -> bool:
        # Older transactions may store just the leaf name instead of the full path.
        return bool(path) and (path in doomed_names or any(path.startswith(p) and path_matches(path, p) for p in doomed_paths))

    orphaned = {t["id"]: {"category_path": None} for t in storage.get_transactions() if belongs(t.get("category_path"))}
    storage.update_transactions(orphaned)
    storage.delete_category(category_id)
    return {"status": "deleted", "id": category_id, "uncategorized_transactions": len(orphaned)}


# ============ BUDGETS ============

@app.get("/budgets")
async def list_budgets():
    return {"budgets": storage.get_budgets()}


def _validate_budget_hierarchy(category_path: Optional[str], amount: Decimal, period: str, exclude_id: Optional[str] = None):
    """A budget may not exceed its parent category's budget, nor undercut its subcategories'."""
    if not category_path:
        return
    same_period = [
        b for b in storage.get_budgets()
        if b.get("period") == period and b.get("id") != exclude_id and b.get("category_path")
    ]

    parts = category_path.split("/")
    for i in range(1, len(parts)):
        parent_path = "/".join(parts[:i])
        for b in same_period:
            if b["category_path"] == parent_path and amount > Decimal(str(b["amount"])):
                raise HTTPException(
                    status_code=400,
                    detail=f"Budget (R{amount:,.2f}) cannot exceed parent category "
                           f"'{parent_path}' budget (R{b['amount']:,.2f})",
                )

    children = [Decimal(str(b["amount"])) for b in same_period if b["category_path"].startswith(category_path + "/")]
    if children and amount < max(children):
        raise HTTPException(
            status_code=400,
            detail=f"Budget (R{amount:,.2f}) cannot be less than an existing subcategory budget (R{max(children):,.2f})",
        )


@app.post("/budgets")
async def create_budget(req: CreateBudgetRequest):
    _validate_budget_hierarchy(req.category_path, req.amount, req.period.value)
    return storage.create_budget(serialize(req.model_dump()))


@app.get("/budgets/status")
async def get_budget_status(from_date: Optional[str] = None, to_date: Optional[str] = None):
    """
    Spending against each budget.

    With no dates, each budget is measured over its current calendar period
    (this month / quarter / year). With from_date and to_date, spending in that
    range is compared to the budget pro-rated to the range's length.
    """
    start = parse_query_date(from_date, "from_date")
    end = parse_query_date(to_date, "to_date")
    if (start is None) != (end is None):
        raise HTTPException(status_code=422, detail="Provide both from_date and to_date, or neither")

    transactions = [t for t in storage.get_transactions() if is_expense(t)]
    today = date.today()
    statuses = []

    for budget in storage.get_budgets():
        period = budget.get("period", BudgetPeriod.MONTHLY.value)
        base_amount = Decimal(str(budget.get("amount", 0)))

        if start and end:
            window_start, window_end = start, end
            days = (end - start).days + 1
            budget_amount = base_amount * Decimal(days) / Decimal(str(PERIOD_DAYS.get(period, PERIOD_DAYS[BudgetPeriod.MONTHLY])))
        else:
            window_start, window_end = current_period_window(period, today)
            budget_amount = base_amount

        # Spending before the budget started (or after it ended) doesn't count against it.
        budget_start = parse_date(budget.get("start_date"))
        budget_end = parse_date(budget.get("end_date"))
        count_from = max(window_start, budget_start) if budget_start else window_start
        count_to = min(window_end, budget_end) if budget_end else window_end

        category = budget.get("category_path")
        tags_filter = set(budget.get("tags_filter") or [])
        spent = sum(
            (Decimal(str(t.get("amount", 0))) for t in transactions
             if in_range(t, count_from, count_to)
             and (not category or path_matches(t.get("category_path"), category))
             and (not tags_filter or tags_filter & set(t.get("tags", [])))),
            Decimal(0),
        )

        percentage = float(spent / budget_amount * 100) if budget_amount > 0 else 0.0
        if percentage >= 100:
            status = BudgetStatus.EXCEEDED
        elif percentage >= 75:
            status = BudgetStatus.APPROACHING
        else:
            status = BudgetStatus.OK

        statuses.append({
            "budget_id": budget.get("id"),
            "category_path": category,
            "period": period,
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            "budget_amount": round(float(budget_amount), 2),
            "spent_amount": float(spent),
            "percentage": percentage,
            "status": status.value,
            "remaining": round(float(budget_amount - spent), 2),
        })

    return {"statuses": statuses}


@app.get("/budgets/{budget_id}")
async def get_budget(budget_id: str):
    budget = storage.get_budget(budget_id)
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    return budget


@app.put("/budgets/{budget_id}")
async def update_budget(budget_id: str, req: UpdateBudgetRequest):
    """Update the fields that are sent."""
    existing = storage.get_budget(budget_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Budget not found")

    updates = serialize(req.model_dump(exclude_unset=True))
    merged = {**existing, **updates}
    _validate_budget_hierarchy(
        merged.get("category_path"), Decimal(str(merged["amount"])), merged.get("period"), exclude_id=budget_id
    )
    return storage.update_budget(budget_id, updates)


@app.delete("/budgets/{budget_id}")
async def delete_budget(budget_id: str):
    try:
        storage.delete_budget(budget_id)
    except NotFoundError as e:
        raise not_found(e)
    return {"status": "deleted", "id": budget_id}


# ============ MERCHANTS ============

@app.get("/merchants")
async def list_merchants():
    return {"merchants": list(storage.get_merchants().values())}


@app.post("/merchants")
async def create_merchant(req: CreateMerchantRequest):
    return storage.create_merchant(req.model_dump())


@app.get("/merchants/{merchant_id}")
async def get_merchant(merchant_id: str):
    merchants = storage.get_merchants()
    if merchant_id not in merchants:
        raise HTTPException(status_code=404, detail="Merchant not found")
    return merchants[merchant_id]


@app.patch("/merchants/{merchant_id}")
async def update_merchant(merchant_id: str, req: UpdateMerchantRequest):
    try:
        return storage.update_merchant(merchant_id, req.model_dump(exclude_unset=True))
    except NotFoundError as e:
        raise not_found(e)


@app.delete("/merchants/{merchant_id}")
async def delete_merchant(merchant_id: str):
    try:
        storage.delete_merchant(merchant_id)
    except NotFoundError as e:
        raise not_found(e)
    return {"status": "deleted", "id": merchant_id}


# ============ IMPORTS ============

HEADER_KEYWORDS = ["date", "description", "amount", "debit", "credit", "balance", "posting", "transaction"]
DATE_COLUMNS = ["transaction date", "trans date", "posting date", "date"]
DESCRIPTION_COLUMNS = ["description", "narration", "details", "memo", "reference"]
EMPTY_AMOUNTS = {"", "0", "0.00", "-"}


def _find_column(columns: Iterable[str], candidates: List[str]) -> Optional[str]:
    """First column whose name contains a candidate, trying candidates in priority order."""
    columns = [c for c in columns if c]
    for candidate in candidates:
        for column in columns:
            if candidate in column.lower():
                return column
    return None


def _parse_amount(raw: str) -> Decimal:
    clean = raw.replace(",", "").replace("$", "").replace("R", "").replace(" ", "").strip()
    if clean.startswith("(") and clean.endswith(")"):  # accounting-style negative
        clean = "-" + clean[1:-1]
    return Decimal(clean)


def _duplicate_key(tx_date: str, description: Optional[str], amount: float) -> Tuple:
    return (tx_date[:10], (description or "").strip().lower(), round(abs(amount), 2))


def parse_bank_csv(content: str) -> Tuple[List[Dict], int]:
    """
    Parse a bank CSV export into transaction dicts. Returns (rows, skipped_count).
    Handles metadata lines above the header, a signed Amount column, or
    separate Debit/Credit columns.
    """
    lines = content.strip().splitlines()

    header_idx = 0
    for i, line in enumerate(lines[:10]):
        if sum(keyword in line.lower() for keyword in HEADER_KEYWORDS) >= 3:
            header_idx = i
            break

    reader = csv.DictReader(io.StringIO("\n".join(lines[header_idx:])))
    columns = reader.fieldnames or []
    date_col = _find_column(columns, DATE_COLUMNS)
    desc_col = _find_column(columns, DESCRIPTION_COLUMNS)
    amount_col = _find_column(columns, ["amount"])
    debit_col = _find_column(columns, ["debit", "withdrawal"])
    credit_col = _find_column(columns, ["credit", "deposit"])

    if not date_col or not (amount_col or debit_col or credit_col):
        raise HTTPException(
            status_code=400,
            detail=f"Could not find date and amount columns in CSV header: {columns}",
        )

    rows, skipped = [], 0
    for row in reader:
        date_str = (row.get(date_col) or "").strip()
        description = (row.get(desc_col) or "").strip() if desc_col else ""

        amount_str = (row.get(amount_col) or "").strip() if amount_col else ""
        if not amount_str:
            debit = (row.get(debit_col) or "").strip() if debit_col else ""
            credit = (row.get(credit_col) or "").strip() if credit_col else ""
            if debit not in EMPTY_AMOUNTS:
                amount_str = "-" + debit.lstrip("-")  # debit = money out
            elif credit not in EMPTY_AMOUNTS:
                amount_str = credit

        try:
            amount = _parse_amount(amount_str)
            tx_date = date_parser.parse(date_str)
        except (InvalidOperation, ValueError, OverflowError):
            skipped += 1
            continue
        if amount == 0:
            skipped += 1
            continue

        rows.append({
            "date": tx_date.date().isoformat(),
            "description": description or "Bank Transaction",
            "amount": float(abs(amount)),
            "currency": DEFAULT_CURRENCY,
            "category_path": None,
            "merchant": description or "Unknown",
            "tags": ["imported"],
            "transaction_type": (TransactionType.EXPENSE if amount < 0 else TransactionType.INCOME).value,
        })
    return rows, skipped


@app.post("/imports/bank-csv")
async def import_bank_csv(req: BankImportRequest):
    """
    Import a bank CSV. Rows already in the ledger are skipped (a statement can
    legitimately contain identical rows, so each existing row absorbs at most one).
    New transactions get learned merchant categories first, then AI suggestions.
    """
    rows, skipped = parse_bank_csv(req.file_content)

    existing = Counter(
        _duplicate_key(t.get("date", ""), t.get("description"), t.get("amount", 0))
        for t in storage.get_transactions()
    )
    new_rows, duplicates = [], 0
    for row in rows:
        key = _duplicate_key(row["date"], row["description"], row["amount"])
        if existing[key] > 0:
            existing[key] -= 1
            duplicates += 1
        else:
            new_rows.append({**row, "source": f"bank_import_{req.bank_format}"})

    # Learned merchant preferences are applied before anything touches the AI.
    for row in new_rows:
        merchant = storage.get_merchant_by_name(row["description"])
        if merchant and merchant.get("preferred_category"):
            row["category_path"] = merchant["preferred_category"]
    learned = sum(1 for row in new_rows if row["category_path"])

    created = storage.create_transactions(new_rows)
    ai_categorised, ai_error = await _ai_categorise(created)

    logger.info(
        "CSV import: %d imported, %d duplicates, %d skipped, %d learned, %d AI-categorised",
        len(created), duplicates, skipped, learned, ai_categorised,
    )
    return {
        "status": "success",
        "imported": len(created),
        "duplicates": duplicates,
        "skipped": skipped,
        "learned_categorised": learned,
        "ai_categorised": ai_categorised,
        "ai_error": ai_error,
    }


async def _ai_categorise(transactions: List[Dict]) -> Tuple[int, Optional[str]]:
    """Ask the AI to categorise the uncategorized ones. Returns (count, error message)."""
    todo = [t for t in transactions if not t.get("category_path")]
    if not todo:
        return 0, None
    try:
        suggestions = await ai_service.categorise_transactions(todo, category_paths(storage.get_categories()))
    except AiUnavailableError as e:
        logger.warning("Skipping AI categorization: %s", e)
        return 0, str(e)
    storage.update_transactions({tid: {"category_path": path} for tid, path in suggestions.items()})
    return len(suggestions), None


# ============ DUPLICATES ============

@app.get("/duplicates")
async def get_duplicates():
    """
    Groups of transactions that share a date and amount, excluding pairs the
    user has marked as 'not a duplicate'.
    """
    ignored = {tuple(pair) for pair in storage.get_ignored_duplicates()}
    groups = defaultdict(list)
    for t in storage.get_transactions():
        groups[((t.get("date") or "")[:10], round(float(t.get("amount", 0)), 2))].append(t)

    result = []
    for (tx_date, amount), members in sorted(groups.items(), reverse=True):
        # Keep a transaction if it still has at least one un-ignored partner in the group.
        kept = [
            t for t in members
            if any(o["id"] != t["id"] and tuple(sorted((t["id"], o["id"]))) not in ignored for o in members)
        ]
        if len(kept) >= 2:
            result.append({"date": tx_date, "amount": amount, "transactions": kept})
    return {"groups": result}


@app.post("/duplicates/ignore")
async def ignore_duplicates(req: IgnoreDuplicatesRequest):
    """Mark transaction pairs as 'not a duplicate' so they stop being reported."""
    if any(len(pair) != 2 for pair in req.pairs):
        raise HTTPException(status_code=422, detail="Each pair must contain exactly two transaction IDs")
    storage.add_ignored_duplicates(req.pairs)
    return {"status": "ok"}


# ============ AI ============

@app.post("/ai/categorise")
async def ai_categorise_transactions():
    """Ask the AI to categorise every uncategorized transaction."""
    uncategorised = [t for t in storage.get_transactions() if not t.get("category_path")]
    count, error = await _ai_categorise(uncategorised)
    if error:
        raise HTTPException(status_code=503, detail=error)
    return {"categorised": count, "total_processed": len(uncategorised)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
