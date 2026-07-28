"""
HTTP client for communicating with the Budget App backend.
Synchronous version for Qt/PySide6 compatibility.
"""
import httpx
from typing import List, Optional, Dict, Any


class BudgetAppClient:
    """Synchronous client for Budget App API."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.Client(base_url=base_url, timeout=30.0)

    def close(self):
        """Close the HTTP client."""
        self.client.close()

    # ============ HEALTH ============

    def health(self) -> bool:
        """Check backend health."""
        try:
            response = self.client.get("/health")
            return response.status_code == 200
        except:
            return False

    # ============ TRANSACTIONS ============

    def list_transactions(
        self,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        category_path: Optional[str] = None,
        merchant: Optional[str] = None,
        tags: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> Dict[str, Any]:
        """List transactions with optional filters."""
        params = {
            "skip": skip,
            "limit": limit
        }
        if from_date:
            params["from_date"] = from_date
        if to_date:
            params["to_date"] = to_date
        if category_path:
            params["category_path"] = category_path
        if merchant:
            params["merchant"] = merchant
        if tags:
            params["tags"] = tags

        response = self.client.get("/transactions", params=params)
        response.raise_for_status()
        return response.json()

    def get_transaction(self, transaction_id: str) -> Dict[str, Any]:
        """Get a specific transaction."""
        response = self.client.get(f"/transactions/{transaction_id}")
        response.raise_for_status()
        return response.json()

    def create_transaction(
        self,
        date: str,
        description: str,
        amount: float,
        currency: str = "USD",
        category_path: Optional[str] = None,
        merchant: Optional[str] = None,
        tags: List[str] = None,
        transaction_type: str = "expense",
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new transaction."""
        payload = {
            "date": date,
            "description": description,
            "amount": amount,
            "currency": currency,
            "category_path": category_path,
            "merchant": merchant,
            "tags": tags or [],
            "transaction_type": transaction_type,
            "notes": notes
        }
        response = self.client.post("/transactions", json=payload)
        response.raise_for_status()
        return response.json()
    
    def smart_create_transaction(self, description: str, amount: str) -> Dict[str, Any]:
        """Create transaction with AI - just description and amount needed."""
        response = self.client.post(
            "/transactions/smart",
            params={"description": description, "amount": amount}
        )
        response.raise_for_status()
        return response.json()

    def update_transaction(
        self,
        transaction_id: str,
        **updates
    ) -> Dict[str, Any]:
        """Update a transaction."""
        response = self.client.patch(f"/transactions/{transaction_id}", json=updates)
        response.raise_for_status()
        return response.json()

    def delete_transaction(self, transaction_id: str):
        """Delete a transaction."""
        response = self.client.delete(f"/transactions/{transaction_id}")
        response.raise_for_status()
        return response.json()

    def get_unknown_transactions(self, skip: int = 0, limit: int = 100) -> Dict[str, Any]:
        """Get transactions with unknown categories."""
        response = self.client.get(
            "/transactions/unknown",
            params={"skip": skip, "limit": limit}
        )
        response.raise_for_status()
        return response.json()

    # ============ CATEGORIES ============

    def get_categories(self) -> Dict[str, Any]:
        """Get the category tree."""
        response = self.client.get("/categories")
        response.raise_for_status()
        return response.json()

    def create_category(
        self,
        name: str,
        parent_id: Optional[str] = None,
        icon: Optional[str] = None,
        color: Optional[str] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new category."""
        payload = {
            "name": name,
            "parent_id": parent_id,
            "icon": icon,
            "color": color,
            "description": description
        }
        response = self.client.post("/categories", json=payload)
        response.raise_for_status()
        return response.json()
    
    def delete_category(self, category_id: str) -> Dict[str, Any]:
        """Delete a category and all its children."""
        response = self.client.delete(f"/categories/{category_id}")
        response.raise_for_status()
        return response.json()

    def update_categories(self, tree: Dict[str, Any]) -> Dict[str, Any]:
        """Replace the entire category tree."""
        response = self.client.put("/categories", json=tree)
        response.raise_for_status()
        return response.json()
    
    def update_category(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update a single category."""
        category_id = updates.pop('id')
        response = self.client.patch(f"/categories/{category_id}", json=updates)
        response.raise_for_status()
        return response.json()

    # ============ BUDGETS ============

    def list_budgets(self) -> Dict[str, Any]:
        """List all budgets."""
        response = self.client.get("/budgets")
        response.raise_for_status()
        return response.json()

    def get_budget(self, budget_id: str) -> Dict[str, Any]:
        """Get a specific budget."""
        response = self.client.get(f"/budgets/{budget_id}")
        response.raise_for_status()
        return response.json()

    def create_budget(
        self,
        amount: float,
        period: str,
        start_date: str,
        category_path: Optional[str] = None,
        end_date: Optional[str] = None,
        tags_filter: List[str] = None,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new budget."""
        payload = {
            "category_path": category_path,
            "amount": amount,
            "period": period,
            "start_date": start_date,
            "end_date": end_date,
            "tags_filter": tags_filter or [],
            "notes": notes
        }
        response = self.client.post("/budgets", json=payload)
        response.raise_for_status()
        return response.json()

    def delete_budget(self, budget_id: str):
        """Delete a budget."""
        response = self.client.delete(f"/budgets/{budget_id}")
        response.raise_for_status()
        return response.json()
    
    def update_budget(self, budget_id: str, **kwargs) -> Dict[str, Any]:
        """Update an existing budget."""
        response = self.client.put(f"/budgets/{budget_id}", json=kwargs)
        response.raise_for_status()
        return response.json()

    def get_budget_status(self) -> Dict[str, Any]:
        """Get status of all budgets."""
        response = self.client.get("/budgets/status")
        response.raise_for_status()
        return response.json()

    # ============ MERCHANTS ============

    def list_merchants(self) -> Dict[str, Any]:
        """List all merchants."""
        response = self.client.get("/merchants")
        response.raise_for_status()
        return response.json()

    def get_merchant(self, merchant_id: str) -> Dict[str, Any]:
        """Get a specific merchant."""
        response = self.client.get(f"/merchants/{merchant_id}")
        response.raise_for_status()
        return response.json()

    def create_merchant(
        self,
        name: str,
        aliases: List[str] = None,
        default_category: Optional[str] = None,
        patterns: List[str] = None,
        confidence: float = 1.0,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new merchant."""
        payload = {
            "name": name,
            "aliases": aliases or [],
            "default_category": default_category,
            "patterns": patterns or [],
            "confidence": confidence,
            "notes": notes
        }
        response = self.client.post("/merchants", json=payload)
        response.raise_for_status()
        return response.json()

    def update_merchant(
        self,
        merchant_id: str,
        **updates
    ) -> Dict[str, Any]:
        """Update a merchant."""
        response = self.client.patch(f"/merchants/{merchant_id}", json=updates)
        response.raise_for_status()
        return response.json()

    def delete_merchant(self, merchant_id: str):
        """Delete a merchant."""
        response = self.client.delete(f"/merchants/{merchant_id}")
        response.raise_for_status()
        return response.json()

    # ============ IMPORTS ============

    def import_bank_csv(
        self,
        csv_content: str,
        bank_format: str = "generic"
    ) -> Dict[str, Any]:
        """Import transactions from bank CSV."""
        payload = {
            "file_content": csv_content,
            "bank_format": bank_format
        }
        response = self.client.post("/imports/bank-csv", json=payload)
        response.raise_for_status()
        return response.json()

    def import_text(
        self,
        text: str,
        source_type: str = "pasted"
    ) -> Dict[str, Any]:
        """
        Import transactions from pasted text using AI parsing.
        No OCR required - AI figures out what it is and extracts transactions.
        """
        payload = {
            "text": text,
            "source_type": source_type
        }
        response = self.client.post("/imports/text", json=payload)
        response.raise_for_status()
        return response.json()

    def import_image(
        self,
        file_path: str
    ) -> Dict[str, Any]:
        """
        Import transactions from an image or PDF (receipt or bank statement).
        Uses OCR + AI to classify and extract transactions.
        """
        with open(file_path, 'rb') as f:
            files = {'file': (file_path.split('\\')[-1].split('/')[-1], f)}
            response = self.client.post("/imports/image", files=files)
            response.raise_for_status()
            return response.json()

    # ============ RECONCILIATION ============

    def get_reconciliation_candidates(self) -> Dict[str, Any]:
        """Get potential reconciliation matches."""
        response = self.client.get("/reconciliation")
        response.raise_for_status()
        return response.json()

    # ============ AI ============

    def ai_categorise_transactions(self) -> Dict[str, Any]:
        """Use AI to suggest categories."""
        response = self.client.post("/ai/categorise")
        response.raise_for_status()
        return response.json()

    def ai_enrich_merchant(
        self,
        merchant_name: str,
        description: str
    ) -> Dict[str, Any]:
        """Use AI to enrich merchant information."""
        params = {
            "merchant_name": merchant_name,
            "description": description
        }
        response = self.client.post("/ai/enrich-merchant", params=params)
        response.raise_for_status()
        return response.json()

        response.raise_for_status()
        return response.json()
