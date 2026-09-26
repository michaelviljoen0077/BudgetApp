"""
Request models and enums for the Budget App API.
Stored records are plain dicts; see storage.py for the on-disk format.
"""
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

DEFAULT_CURRENCY = "ZAR"


class BudgetStatus(str, Enum):
    """Budget status indicator."""
    OK = "ok"
    APPROACHING = "approaching"  # 75-99% of budget
    EXCEEDED = "exceeded"  # 100%+


class BudgetPeriod(str, Enum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class TransactionType(str, Enum):
    """Type of transaction."""
    EXPENSE = "expense"
    INCOME = "income"
    TRANSFER = "transfer"


# ============ TRANSACTIONS ============

class CreateTransactionRequest(BaseModel):
    date: datetime
    description: str
    amount: Decimal
    currency: str = DEFAULT_CURRENCY
    category_path: Optional[str] = None
    merchant: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    transaction_type: TransactionType = TransactionType.EXPENSE
    notes: Optional[str] = None


class SmartTransactionRequest(BaseModel):
    description: str
    amount: Decimal


class UpdateTransactionRequest(BaseModel):
    """Partial update: only fields that are sent are changed."""
    date: Optional[datetime] = None
    description: Optional[str] = None
    amount: Optional[Decimal] = None
    category_path: Optional[str] = None
    merchant: Optional[str] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None
    transaction_type: Optional[TransactionType] = None


# ============ CATEGORIES ============

class CategoryNode(BaseModel):
    id: str
    name: str
    parent_id: Optional[str] = None
    children: List[str] = Field(default_factory=list)
    icon: Optional[str] = None
    color: Optional[str] = None
    description: Optional[str] = None


class CategoryTree(BaseModel):
    nodes: Dict[str, CategoryNode] = Field(default_factory=dict)
    root_ids: List[str] = Field(default_factory=list)


class CreateCategoryRequest(BaseModel):
    name: str
    parent_id: Optional[str] = None  # category ID, or a category name
    icon: Optional[str] = None
    color: Optional[str] = None
    description: Optional[str] = None


class UpdateCategoryRequest(BaseModel):
    """Partial update. Sending parent_id=null moves the category to the root."""
    name: Optional[str] = None
    parent_id: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None


# ============ BUDGETS ============

class CreateBudgetRequest(BaseModel):
    category_path: Optional[str] = None
    amount: Decimal = Field(gt=0)
    period: BudgetPeriod = BudgetPeriod.MONTHLY
    start_date: datetime
    end_date: Optional[datetime] = None
    tags_filter: List[str] = Field(default_factory=list)
    notes: Optional[str] = None


class UpdateBudgetRequest(BaseModel):
    category_path: Optional[str] = None
    amount: Optional[Decimal] = Field(default=None, gt=0)
    period: Optional[BudgetPeriod] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    tags_filter: Optional[List[str]] = None
    notes: Optional[str] = None


# ============ MERCHANTS ============

class CreateMerchantRequest(BaseModel):
    name: str
    aliases: List[str] = Field(default_factory=list)
    preferred_category: Optional[str] = None
    confidence: float = 1.0
    notes: Optional[str] = None


class UpdateMerchantRequest(BaseModel):
    name: Optional[str] = None
    aliases: Optional[List[str]] = None
    preferred_category: Optional[str] = None
    confidence: Optional[float] = None
    notes: Optional[str] = None


# ============ IMPORTS / DUPLICATES ============

class BankImportRequest(BaseModel):
    file_content: str
    bank_format: str = "generic"


class IgnoreDuplicatesRequest(BaseModel):
    """Pairs of transaction IDs the user confirmed are not duplicates."""
    pairs: List[List[str]]
