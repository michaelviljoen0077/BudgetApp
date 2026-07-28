"""
Data models for the Budget App backend using Pydantic.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
from enum import Enum
from pydantic import BaseModel, Field


class BudgetStatus(str, Enum):
    """Budget status indicator."""
    OK = "ok"
    APPROACHING = "approaching"  # 75-99% of budget
    EXCEEDED = "exceeded"  # 100%+


class TransactionType(str, Enum):
    """Type of transaction."""
    EXPENSE = "expense"
    INCOME = "income"
    TRANSFER = "transfer"


class Transaction(BaseModel):
    """Represents a single transaction."""
    id: str = Field(default_factory=lambda: None)  # UUID, generated if not provided
    date: datetime
    description: str
    amount: Decimal
    currency: str = "USD"
    category_path: Optional[str] = None  # e.g., "Food/Takeouts/McDonald's"
    merchant: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    transaction_type: TransactionType = TransactionType.EXPENSE
    notes: Optional[str] = None
    receipt_id: Optional[str] = None  # Link to receipt if reconciled
    source: str = "manual"  # "manual", "bank_import", etc.
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class CategoryNode(BaseModel):
    """Represents a node in the category tree."""
    id: str
    name: str
    parent_id: Optional[str] = None
    children: List[str] = Field(default_factory=list)  # IDs of child nodes
    icon: Optional[str] = None
    color: Optional[str] = None
    description: Optional[str] = None
    is_default: bool = False


class CategoryTree(BaseModel):
    """Root container for category tree."""
    nodes: Dict[str, CategoryNode] = Field(default_factory=dict)  # id -> CategoryNode
    root_ids: List[str] = Field(default_factory=list)  # IDs of root nodes


class Budget(BaseModel):
    """Represents a budget definition."""
    id: str
    category_path: Optional[str] = None  # Can be on any node
    amount: Decimal
    period: str  # "monthly", "quarterly", "yearly", "custom"
    start_date: datetime
    end_date: Optional[datetime] = None
    tags_filter: List[str] = Field(default_factory=list)  # Optional: filter by tags
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class BudgetStatusResponse(BaseModel):
    """Budget status with current spending."""
    budget_id: str
    category_path: Optional[str]
    period: str
    budget_amount: Decimal
    spent_amount: Decimal
    percentage: float
    status: BudgetStatus
    remaining: Decimal


class Merchant(BaseModel):
    """Merchant dictionary entry for categorization rules."""
    id: str
    name: str
    aliases: List[str] = Field(default_factory=list)
    default_category: Optional[str] = None
    patterns: List[str] = Field(default_factory=list)  # Regex patterns for matching
    confidence: float = 1.0  # 0-1 confidence level
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ReconciliationMatch(BaseModel):
    """Represents a potential match between receipt and bank transaction."""
    id: str
    transaction_id: str
    receipt_id: str
    confidence: float  # 0-1
    match_reason: str  # "amount_date_match", "amount_merchant_match", etc.
    is_confirmed: bool = False


class BankImportRequest(BaseModel):
    """Request to import bank CSV."""
    file_content: str  # CSV content
    bank_format: str = "generic"  # "generic", "chase", "bofa", etc.
    start_row: int = 1


class CreateTransactionRequest(BaseModel):
    """Request to create a new transaction."""
    date: datetime
    description: str
    amount: Decimal
    currency: str = "USD"
    category_path: Optional[str] = None
    merchant: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    transaction_type: TransactionType = TransactionType.EXPENSE
    notes: Optional[str] = None


class ImportTextRequest(BaseModel):
    """Request to import transactions from pasted text (AI parsing)."""
    text: str
    source_type: Optional[str] = "pasted"  # "pasted", "receipt", "statement"


class UpdateTransactionRequest(BaseModel):
    """Request to update a transaction."""
    date: Optional[datetime] = None
    description: Optional[str] = None
    amount: Optional[Decimal] = None
    category_path: Optional[str] = None
    merchant: Optional[str] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None


class CreateCategoryRequest(BaseModel):
    """Request to create a new category."""
    name: str
    parent_id: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    description: Optional[str] = None


class CreateBudgetRequest(BaseModel):
    """Request to create a budget."""
    category_path: Optional[str] = None
    amount: Decimal
    period: str
    start_date: datetime
    end_date: Optional[datetime] = None
    tags_filter: List[str] = Field(default_factory=list)
    notes: Optional[str] = None
