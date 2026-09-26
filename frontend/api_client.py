"""
HTTP client for communicating with the Budget App backend.
Synchronous, for use from the Qt event loop.
"""
from typing import Any, Dict, List, Optional

import httpx

# Imports and AI categorisation call a local LLM once per transaction and can take minutes.
SLOW_REQUEST_TIMEOUT = 600.0


class ApiError(Exception):
    """A request to the backend failed; the message is the backend's explanation."""


class BudgetAppClient:
    """Synchronous client for the Budget App API."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.Client(base_url=base_url, timeout=30.0)

    def close(self):
        self.client.close()

    def _request(self, method: str, url: str, **kwargs) -> Any:
        try:
            response = self.client.request(method, url, **kwargs)
        except httpx.TransportError as e:
            raise ApiError(f"Cannot reach the backend at {self.base_url} ({e}). Is it running?") from e
        if response.is_error:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            raise ApiError(f"{detail} (HTTP {response.status_code})")
        return response.json()

    # ============ HEALTH ============

    def health(self) -> bool:
        try:
            return self.client.get("/health").status_code == 200
        except httpx.HTTPError:
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
        limit: int = 100,
    ) -> Dict[str, Any]:
        params = {"skip": skip, "limit": limit, "from_date": from_date, "to_date": to_date,
                  "category_path": category_path, "merchant": merchant, "tags": tags}
        return self._request("GET", "/transactions", params={k: v for k, v in params.items() if v is not None})

    def get_transaction(self, transaction_id: str) -> Dict[str, Any]:
        return self._request("GET", f"/transactions/{transaction_id}")

    def create_transaction(
        self,
        date: str,
        description: str,
        amount: float,
        currency: str = "ZAR",
        category_path: Optional[str] = None,
        merchant: Optional[str] = None,
        tags: Optional[List[str]] = None,
        transaction_type: str = "expense",
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload = {
            "date": date, "description": description, "amount": amount, "currency": currency,
            "category_path": category_path, "merchant": merchant, "tags": tags or [],
            "transaction_type": transaction_type, "notes": notes,
        }
        return self._request("POST", "/transactions", json=payload)

    def smart_create_transaction(self, description: str, amount: str) -> Dict[str, Any]:
        """Create an expense from a description and amount; the backend picks the category."""
        return self._request(
            "POST", "/transactions/smart",
            json={"description": description, "amount": amount},
            timeout=SLOW_REQUEST_TIMEOUT,
        )

    def update_transaction(self, transaction_id: str, **updates) -> Dict[str, Any]:
        return self._request("PATCH", f"/transactions/{transaction_id}", json=updates)

    def delete_transaction(self, transaction_id: str) -> Dict[str, Any]:
        return self._request("DELETE", f"/transactions/{transaction_id}")

    def get_unknown_transactions(self, skip: int = 0, limit: int = 100) -> Dict[str, Any]:
        return self._request("GET", "/transactions/unknown", params={"skip": skip, "limit": limit})

    # ============ CATEGORIES ============

    def get_categories(self) -> Dict[str, Any]:
        return self._request("GET", "/categories")

    def create_category(
        self,
        name: str,
        parent_id: Optional[str] = None,
        icon: Optional[str] = None,
        color: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload = {"name": name, "parent_id": parent_id, "icon": icon, "color": color, "description": description}
        return self._request("POST", "/categories", json=payload)

    def update_category(self, category_id: str, **updates) -> Dict[str, Any]:
        """Update a category; pass parent_id=None to move it to the top level."""
        return self._request("PATCH", f"/categories/{category_id}", json=updates)

    def delete_category(self, category_id: str) -> Dict[str, Any]:
        """Delete a category and all its children."""
        return self._request("DELETE", f"/categories/{category_id}")

    # ============ BUDGETS ============

    def list_budgets(self) -> Dict[str, Any]:
        return self._request("GET", "/budgets")

    def get_budget(self, budget_id: str) -> Dict[str, Any]:
        return self._request("GET", f"/budgets/{budget_id}")

    def create_budget(
        self,
        amount: float,
        period: str,
        start_date: str,
        category_path: Optional[str] = None,
        end_date: Optional[str] = None,
        tags_filter: Optional[List[str]] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload = {
            "category_path": category_path, "amount": amount, "period": period, "start_date": start_date,
            "end_date": end_date, "tags_filter": tags_filter or [], "notes": notes,
        }
        return self._request("POST", "/budgets", json=payload)

    def update_budget(self, budget_id: str, **updates) -> Dict[str, Any]:
        return self._request("PUT", f"/budgets/{budget_id}", json=updates)

    def delete_budget(self, budget_id: str) -> Dict[str, Any]:
        return self._request("DELETE", f"/budgets/{budget_id}")

    def get_budget_status(self, from_date: Optional[str] = None, to_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Spending against each budget. Without dates: the current month/quarter/year.
        With both dates: that range, against the budget pro-rated to its length.
        """
        params = {"from_date": from_date, "to_date": to_date} if from_date and to_date else {}
        return self._request("GET", "/budgets/status", params=params)

    # ============ MERCHANTS ============

    def list_merchants(self) -> Dict[str, Any]:
        return self._request("GET", "/merchants")

    def delete_merchant(self, merchant_id: str) -> Dict[str, Any]:
        return self._request("DELETE", f"/merchants/{merchant_id}")

    # ============ IMPORTS ============

    def import_bank_csv(self, csv_content: str, bank_format: str = "generic") -> Dict[str, Any]:
        return self._request(
            "POST", "/imports/bank-csv",
            json={"file_content": csv_content, "bank_format": bank_format},
            timeout=SLOW_REQUEST_TIMEOUT,
        )

    # ============ DUPLICATES ============

    def get_duplicates(self) -> Dict[str, Any]:
        """Groups of transactions sharing a date and amount (minus ignored pairs)."""
        return self._request("GET", "/duplicates")

    def ignore_duplicates(self, pairs: List[List[str]]) -> Dict[str, Any]:
        """Mark transaction ID pairs as 'not a duplicate'."""
        return self._request("POST", "/duplicates/ignore", json={"pairs": pairs})

    # ============ AI ============

    def ai_categorise_transactions(self) -> Dict[str, Any]:
        return self._request("POST", "/ai/categorise", timeout=SLOW_REQUEST_TIMEOUT)
