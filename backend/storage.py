"""
JSON-based storage layer for the Budget App.
Handles atomic reads and writes for ledger, categories, budgets, and merchants.
"""
import json
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from decimal import Decimal
import tempfile
import shutil
from functools import wraps


class StorageError(Exception):
    """Base exception for storage operations."""
    pass


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal types."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class Storage:
    """Manages JSON file storage with atomic writes."""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.ledger_file = self.data_dir / "ledger.json"
        self.categories_file = self.data_dir / "categories.json"
        self.budgets_file = self.data_dir / "budgets.json"
        self.merchants_file = self.data_dir / "merchants.json"
        
        # Initialize files if they don't exist
        self._ensure_files_exist()

    def _ensure_files_exist(self):
        """Ensure all storage files exist with proper initial structure."""
        if not self.ledger_file.exists():
            self._atomic_write(self.ledger_file, {"transactions": []})
        
        if not self.categories_file.exists():
            self._atomic_write(self.categories_file, {"nodes": {}, "root_ids": []})
        
        if not self.budgets_file.exists():
            self._atomic_write(self.budgets_file, {"budgets": []})
        
        if not self.merchants_file.exists():
            self._atomic_write(self.merchants_file, {"merchants": {}})

    def _atomic_write(self, file_path: Path, data: Any):
        """
        Write data to file atomically using temp file + rename.
        Prevents corruption if write is interrupted.
        """
        with tempfile.NamedTemporaryFile(
            mode='w',
            dir=self.data_dir,
            delete=False,
            suffix='.tmp'
        ) as tmp_file:
            json.dump(data, tmp_file, cls=DecimalEncoder, indent=2)
            tmp_path = tmp_file.name
        
        # Atomic rename
        shutil.move(tmp_path, file_path)

    def _read_file(self, file_path: Path) -> Dict:
        """Read JSON file."""
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            raise StorageError(f"File not found: {file_path}")
        except json.JSONDecodeError as e:
            raise StorageError(f"Invalid JSON in {file_path}: {e}")

    # ============ TRANSACTIONS ============

    def get_transactions(self) -> List[Dict]:
        """Get all transactions."""
        data = self._read_file(self.ledger_file)
        return data.get("transactions", [])

    def get_transaction(self, transaction_id: str) -> Optional[Dict]:
        """Get a specific transaction by ID."""
        transactions = self.get_transactions()
        return next((t for t in transactions if t.get("id") == transaction_id), None)

    def create_transaction(self, transaction_data: Dict) -> Dict:
        """Create a new transaction."""
        transaction_data["id"] = str(uuid.uuid4())
        transaction_data["created_at"] = datetime.utcnow().isoformat()
        transaction_data["updated_at"] = datetime.utcnow().isoformat()
        
        data = self._read_file(self.ledger_file)
        data["transactions"].append(transaction_data)
        self._atomic_write(self.ledger_file, data)
        
        return transaction_data

    def update_transaction(self, transaction_id: str, updates: Dict) -> Dict:
        """Update an existing transaction."""
        data = self._read_file(self.ledger_file)
        transactions = data.get("transactions", [])
        
        transaction = next((t for t in transactions if t.get("id") == transaction_id), None)
        if not transaction:
            raise StorageError(f"Transaction not found: {transaction_id}")
        
        updates["updated_at"] = datetime.utcnow().isoformat()
        transaction.update(updates)
        
        self._atomic_write(self.ledger_file, data)
        return transaction

    def delete_transaction(self, transaction_id: str):
        """Delete a transaction."""
        data = self._read_file(self.ledger_file)
        original_count = len(data.get("transactions", []))
        print(f"Before delete: {original_count} transactions")
        
        data["transactions"] = [
            t for t in data.get("transactions", [])
            if t.get("id") != transaction_id
        ]
        
        new_count = len(data.get("transactions", []))
        print(f"After delete: {new_count} transactions")
        
        if original_count == new_count:
            print(f"WARNING: Transaction {transaction_id} not found!")
        
        self._atomic_write(self.ledger_file, data)
        print(f"Deleted transaction {transaction_id} and saved to disk")

    # ============ CATEGORIES ============

    def get_categories(self) -> Dict:
        """Get the entire category tree."""
        return self._read_file(self.categories_file)

    def create_category(self, category_data: Dict) -> Dict:
        """Create a new category node."""
        category_data["id"] = str(uuid.uuid4())
        
        data = self._read_file(self.categories_file)
        data["nodes"][category_data["id"]] = category_data
        
        # Add to parent's children if parent exists
        parent_id = category_data.get("parent_id")
        if parent_id and parent_id in data["nodes"]:
            if "children" not in data["nodes"][parent_id]:
                data["nodes"][parent_id]["children"] = []
            data["nodes"][parent_id]["children"].append(category_data["id"])
        else:
            # Add as root if no parent
            data["root_ids"].append(category_data["id"])
        
        self._atomic_write(self.categories_file, data)
        return category_data

    def update_categories(self, categories_data: Dict):
        """Replace the entire category tree."""
        self._atomic_write(self.categories_file, categories_data)

    def delete_category(self, category_id: str):
        """Delete a category and all its children recursively."""
        data = self._read_file(self.categories_file)
        
        if category_id not in data["nodes"]:
            raise StorageError(f"Category not found: {category_id}")
        
        # Get all IDs to delete (category + all descendants)
        ids_to_delete = self._get_category_descendants(category_id, data["nodes"])
        ids_to_delete.append(category_id)
        
        print(f"Deleting category {category_id} and {len(ids_to_delete)-1} descendants")
        
        # Remove from parent's children list or root_ids
        category = data["nodes"][category_id]
        parent_id = category.get("parent_id")
        
        if parent_id and parent_id in data["nodes"]:
            if "children" in data["nodes"][parent_id]:
                data["nodes"][parent_id]["children"] = [
                    c for c in data["nodes"][parent_id]["children"] if c != category_id
                ]
        elif category_id in data["root_ids"]:
            data["root_ids"].remove(category_id)
        
        # Delete all nodes
        for node_id in ids_to_delete:
            if node_id in data["nodes"]:
                del data["nodes"][node_id]
        
        self._atomic_write(self.categories_file, data)
    
    def _get_category_descendants(self, category_id: str, nodes: Dict) -> List[str]:
        """Recursively get all descendant IDs of a category."""
        descendants = []
        if category_id in nodes:
            for child_id in nodes[category_id].get("children", []):
                descendants.append(child_id)
                descendants.extend(self._get_category_descendants(child_id, nodes))
        return descendants

    # ============ BUDGETS ============

    def get_budgets(self) -> List[Dict]:
        """Get all budgets."""
        data = self._read_file(self.budgets_file)
        return data.get("budgets", [])

    def create_budget(self, budget_data: Dict) -> Dict:
        """Create a new budget."""
        budget_data["id"] = str(uuid.uuid4())
        budget_data["created_at"] = datetime.utcnow().isoformat()
        budget_data["updated_at"] = datetime.utcnow().isoformat()
        
        data = self._read_file(self.budgets_file)
        data["budgets"].append(budget_data)
        self._atomic_write(self.budgets_file, data)
        
        return budget_data

    def update_budget(self, budget_id: str, updates: Dict) -> Dict:
        """Update an existing budget."""
        data = self._read_file(self.budgets_file)
        budgets = data.get("budgets", [])
        
        budget = next((b for b in budgets if b.get("id") == budget_id), None)
        if not budget:
            raise StorageError(f"Budget not found: {budget_id}")
        
        updates["updated_at"] = datetime.utcnow().isoformat()
        budget.update(updates)
        
        self._atomic_write(self.budgets_file, data)
        return budget

    def delete_budget(self, budget_id: str):
        """Delete a budget."""
        data = self._read_file(self.budgets_file)
        data["budgets"] = [
            b for b in data.get("budgets", [])
            if b.get("id") != budget_id
        ]
        self._atomic_write(self.budgets_file, data)

    # ============ MERCHANTS ============

    def get_merchants(self) -> Dict[str, Dict]:
        """Get all merchants."""
        data = self._read_file(self.merchants_file)
        return data.get("merchants", {})

    def create_merchant(self, merchant_data: Dict) -> Dict:
        """Create a new merchant entry."""
        merchant_data["id"] = str(uuid.uuid4())
        merchant_data["created_at"] = datetime.utcnow().isoformat()
        merchant_data["updated_at"] = datetime.utcnow().isoformat()
        
        data = self._read_file(self.merchants_file)
        data["merchants"][merchant_data["id"]] = merchant_data
        self._atomic_write(self.merchants_file, data)
        
        return merchant_data

    def update_merchant(self, merchant_id: str, updates: Dict) -> Dict:
        """Update an existing merchant."""
        data = self._read_file(self.merchants_file)
        merchants = data.get("merchants", {})
        
        if merchant_id not in merchants:
            raise StorageError(f"Merchant not found: {merchant_id}")
        
        updates["updated_at"] = datetime.utcnow().isoformat()
        merchants[merchant_id].update(updates)
        
        self._atomic_write(self.merchants_file, data)
        return merchants[merchant_id]

    def delete_merchant(self, merchant_id: str):
        """Delete a merchant."""
        data = self._read_file(self.merchants_file)
        merchants = data.get("merchants", {})
        
        if merchant_id in merchants:
            del merchants[merchant_id]
            self._atomic_write(self.merchants_file, data)

    def get_merchant_by_name(self, name: str) -> Optional[Dict]:
        """Find a merchant by name or alias."""
        merchants = self.get_merchants()
        for merchant in merchants.values():
            if merchant["name"].lower() == name.lower():
                return merchant
            if any(alias.lower() == name.lower() for alias in merchant.get("aliases", [])):
                return merchant
        return None
