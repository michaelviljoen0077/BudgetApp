"""
JSON-based storage layer for the Budget App.
Handles atomic reads and writes for ledger, categories, budgets, and merchants.
"""
import json
import os
import tempfile
import uuid
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

# Data lives next to this module regardless of the current working directory.
DEFAULT_DATA_DIR = Path(__file__).resolve().parent / "data"


class StorageError(Exception):
    """Base exception for storage operations."""


class NotFoundError(StorageError):
    """Raised when a requested record does not exist."""


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal and datetime types."""

    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


def _now() -> str:
    return datetime.utcnow().isoformat()


class Storage:
    """Manages JSON file storage with atomic writes."""

    def __init__(self, data_dir: Optional[os.PathLike] = None):
        self.data_dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.ledger_file = self.data_dir / "ledger.json"
        self.categories_file = self.data_dir / "categories.json"
        self.budgets_file = self.data_dir / "budgets.json"
        self.merchants_file = self.data_dir / "merchants.json"
        self.ignored_duplicates_file = self.data_dir / "ignored_duplicates.json"

        self._ensure_files_exist()

    def _ensure_files_exist(self):
        """Ensure all storage files exist with proper initial structure."""
        defaults = {
            self.ledger_file: {"transactions": []},
            self.categories_file: {"nodes": {}, "root_ids": []},
            self.budgets_file: {"budgets": []},
            self.merchants_file: {"merchants": {}},
            self.ignored_duplicates_file: [],
        }
        for path, initial in defaults.items():
            if not path.exists():
                self._atomic_write(path, initial)

    def _atomic_write(self, file_path: Path, data: Any):
        """
        Write data to file atomically using temp file + rename.
        Prevents corruption if write is interrupted.
        """
        with tempfile.NamedTemporaryFile(
            mode="w", dir=self.data_dir, delete=False, suffix=".tmp", encoding="utf-8"
        ) as tmp_file:
            json.dump(data, tmp_file, cls=DecimalEncoder, indent=2)
            tmp_path = tmp_file.name
        os.replace(tmp_path, file_path)

    def _read_file(self, file_path: Path) -> Any:
        """Read JSON file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            raise StorageError(f"File not found: {file_path}")
        except json.JSONDecodeError as e:
            raise StorageError(f"Invalid JSON in {file_path}: {e}")

    # ============ TRANSACTIONS ============

    def get_transactions(self) -> List[Dict]:
        """Get all transactions."""
        return self._read_file(self.ledger_file).get("transactions", [])

    def get_transaction(self, transaction_id: str) -> Optional[Dict]:
        """Get a specific transaction by ID."""
        return next((t for t in self.get_transactions() if t.get("id") == transaction_id), None)

    def create_transaction(self, transaction_data: Dict) -> Dict:
        """Create a new transaction."""
        return self.create_transactions([transaction_data])[0]

    def create_transactions(self, transactions: Iterable[Dict]) -> List[Dict]:
        """Create several transactions with a single write."""
        data = self._read_file(self.ledger_file)
        created = []
        for transaction_data in transactions:
            now = _now()
            transaction_data = {**transaction_data, "id": str(uuid.uuid4()), "created_at": now, "updated_at": now}
            data["transactions"].append(transaction_data)
            created.append(transaction_data)
        self._atomic_write(self.ledger_file, data)
        return created

    def update_transaction(self, transaction_id: str, updates: Dict) -> Dict:
        """Update an existing transaction."""
        return self.update_transactions({transaction_id: updates})[0]

    def update_transactions(self, updates_by_id: Dict[str, Dict]) -> List[Dict]:
        """Apply updates to several transactions with a single write."""
        data = self._read_file(self.ledger_file)
        by_id = {t.get("id"): t for t in data.get("transactions", [])}

        missing = [tid for tid in updates_by_id if tid not in by_id]
        if missing:
            raise NotFoundError(f"Transaction not found: {', '.join(missing)}")

        updated = []
        for transaction_id, updates in updates_by_id.items():
            transaction = by_id[transaction_id]
            transaction.update(updates)
            transaction["updated_at"] = _now()
            updated.append(transaction)

        if updated:
            self._atomic_write(self.ledger_file, data)
        return updated

    def delete_transaction(self, transaction_id: str):
        """Delete a transaction."""
        data = self._read_file(self.ledger_file)
        transactions = data.get("transactions", [])
        remaining = [t for t in transactions if t.get("id") != transaction_id]
        if len(remaining) == len(transactions):
            raise NotFoundError(f"Transaction not found: {transaction_id}")
        data["transactions"] = remaining
        self._atomic_write(self.ledger_file, data)

    # ============ CATEGORIES ============

    def get_categories(self) -> Dict:
        """Get the entire category tree."""
        return self._read_file(self.categories_file)

    def create_category(self, category_data: Dict) -> Dict:
        """Create a new category node."""
        category_data = {**category_data, "id": str(uuid.uuid4())}
        category_data.setdefault("children", [])

        data = self._read_file(self.categories_file)
        data.setdefault("root_ids", [])
        data["nodes"][category_data["id"]] = category_data

        parent_id = category_data.get("parent_id")
        if parent_id and parent_id in data["nodes"]:
            data["nodes"][parent_id].setdefault("children", []).append(category_data["id"])
        else:
            category_data["parent_id"] = None
            data["root_ids"].append(category_data["id"])

        self._atomic_write(self.categories_file, data)
        return category_data

    def update_categories(self, categories_data: Dict):
        """Replace the entire category tree."""
        self._atomic_write(self.categories_file, categories_data)

    def delete_category(self, category_id: str):
        """Delete a category and all its children recursively."""
        data = self._read_file(self.categories_file)
        nodes = data["nodes"]

        if category_id not in nodes:
            raise NotFoundError(f"Category not found: {category_id}")

        ids_to_delete = [category_id] + self.get_category_descendants(category_id, nodes)

        parent_id = nodes[category_id].get("parent_id")
        if parent_id and parent_id in nodes:
            nodes[parent_id]["children"] = [
                c for c in nodes[parent_id].get("children", []) if c != category_id
            ]
        if category_id in data.get("root_ids", []):
            data["root_ids"].remove(category_id)

        for node_id in ids_to_delete:
            nodes.pop(node_id, None)

        self._atomic_write(self.categories_file, data)

    def get_category_descendants(self, category_id: str, nodes: Dict) -> List[str]:
        """Recursively get all descendant IDs of a category."""
        descendants = []
        for child_id in nodes.get(category_id, {}).get("children", []):
            descendants.append(child_id)
            descendants.extend(self.get_category_descendants(child_id, nodes))
        return descendants

    # ============ BUDGETS ============

    def get_budgets(self) -> List[Dict]:
        """Get all budgets."""
        return self._read_file(self.budgets_file).get("budgets", [])

    def get_budget(self, budget_id: str) -> Optional[Dict]:
        """Get a specific budget by ID."""
        return next((b for b in self.get_budgets() if b.get("id") == budget_id), None)

    def create_budget(self, budget_data: Dict) -> Dict:
        """Create a new budget."""
        now = _now()
        budget_data = {**budget_data, "id": str(uuid.uuid4()), "created_at": now, "updated_at": now}

        data = self._read_file(self.budgets_file)
        data["budgets"].append(budget_data)
        self._atomic_write(self.budgets_file, data)
        return budget_data

    def update_budget(self, budget_id: str, updates: Dict) -> Dict:
        """Update an existing budget."""
        data = self._read_file(self.budgets_file)
        budget = next((b for b in data.get("budgets", []) if b.get("id") == budget_id), None)
        if not budget:
            raise NotFoundError(f"Budget not found: {budget_id}")

        budget.update(updates)
        budget["updated_at"] = _now()
        self._atomic_write(self.budgets_file, data)
        return budget

    def delete_budget(self, budget_id: str):
        """Delete a budget."""
        data = self._read_file(self.budgets_file)
        budgets = data.get("budgets", [])
        remaining = [b for b in budgets if b.get("id") != budget_id]
        if len(remaining) == len(budgets):
            raise NotFoundError(f"Budget not found: {budget_id}")
        data["budgets"] = remaining
        self._atomic_write(self.budgets_file, data)

    # ============ MERCHANTS ============

    def get_merchants(self) -> Dict[str, Dict]:
        """Get all merchants."""
        return self._read_file(self.merchants_file).get("merchants", {})

    def create_merchant(self, merchant_data: Dict) -> Dict:
        """Create a new merchant entry."""
        now = _now()
        merchant_data = {**merchant_data, "id": str(uuid.uuid4()), "created_at": now, "updated_at": now}

        data = self._read_file(self.merchants_file)
        data["merchants"][merchant_data["id"]] = merchant_data
        self._atomic_write(self.merchants_file, data)
        return merchant_data

    def update_merchant(self, merchant_id: str, updates: Dict) -> Dict:
        """Update an existing merchant."""
        data = self._read_file(self.merchants_file)
        merchants = data.get("merchants", {})
        if merchant_id not in merchants:
            raise NotFoundError(f"Merchant not found: {merchant_id}")

        merchants[merchant_id].update(updates)
        merchants[merchant_id]["updated_at"] = _now()
        self._atomic_write(self.merchants_file, data)
        return merchants[merchant_id]

    def delete_merchant(self, merchant_id: str):
        """Delete a merchant."""
        data = self._read_file(self.merchants_file)
        if data.get("merchants", {}).pop(merchant_id, None) is None:
            raise NotFoundError(f"Merchant not found: {merchant_id}")
        self._atomic_write(self.merchants_file, data)

    def get_merchant_by_name(self, name: str) -> Optional[Dict]:
        """Find a merchant by name or alias (case-insensitive)."""
        wanted = name.strip().lower()
        for merchant in self.get_merchants().values():
            names = [merchant.get("name", "")] + merchant.get("aliases", [])
            if any(n.lower() == wanted for n in names):
                return merchant
        return None

    # ============ IGNORED DUPLICATES ============

    def get_ignored_duplicates(self) -> List[List[str]]:
        """Get transaction ID pairs the user has marked as 'not a duplicate'."""
        return self._read_file(self.ignored_duplicates_file)

    def add_ignored_duplicates(self, pairs: Iterable[Iterable[str]]) -> List[List[str]]:
        """Record transaction ID pairs as 'not a duplicate'. Pairs are stored sorted."""
        ignored = self.get_ignored_duplicates()
        existing = {tuple(p) for p in ignored}
        for pair in pairs:
            key = tuple(sorted(pair))
            if len(key) == 2 and key not in existing:
                existing.add(key)
                ignored.append(list(key))
        self._atomic_write(self.ignored_duplicates_file, ignored)
        return ignored
