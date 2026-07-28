"""
FastAPI backend for the Budget App.
Exposes RESTful API for transactions, categories, budgets, merchants, and reconciliation.
"""
from fastapi import FastAPI, HTTPException, Query, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any
from pathlib import Path
import csv
import io
import re
import json

from models import (
    Transaction, CreateTransactionRequest, UpdateTransactionRequest,
    CategoryNode, CategoryTree, CreateCategoryRequest,
    Budget, CreateBudgetRequest, BudgetStatusResponse, BudgetStatus,
    Merchant, BankImportRequest, ImportTextRequest, ReconciliationMatch, TransactionType
)
from storage import Storage
from ai_service import get_ai_service
from reconciliation import ReconciliationService


# Initialize FastAPI app
app = FastAPI(
    title="Budget App Backend",
    description="Personal expense tracker with tree-based budgeting",
    version="1.0.0"
)

# Add CORS middleware for desktop client
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize storage and AI service
storage = Storage(data_dir="data")
# Options: "noop" (disabled), "local" (Ollama on localhost:11434)
ai_service = get_ai_service(provider="local", model="mistral", vision_model="llava")
reconciliation_service = ReconciliationService(storage)


# ============ HEALTH ============

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


# ============ TRANSACTIONS ============

@app.get("/transactions")
async def list_transactions(
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    category_path: Optional[str] = Query(None),
    merchant: Optional[str] = Query(None),
    tags: Optional[str] = Query(None),  # comma-separated
    skip: int = Query(0),
    limit: int = Query(100)
):
    """List transactions with optional filters."""
    transactions = storage.get_transactions()
    
    # Filter by date range
    if from_date:
        from_dt = datetime.fromisoformat(from_date)
        transactions = [
            t for t in transactions
            if datetime.fromisoformat(t.get("date", "")) >= from_dt
        ]
    
    if to_date:
        to_dt = datetime.fromisoformat(to_date)
        transactions = [
            t for t in transactions
            if datetime.fromisoformat(t.get("date", "")) <= to_dt
        ]
    
    # Filter by category
    if category_path:
        transactions = [
            t for t in transactions
            if t.get("category_path", "").startswith(category_path)
        ]
    
    # Filter by merchant
    if merchant:
        transactions = [
            t for t in transactions
            if t.get("merchant", "").lower() == merchant.lower()
        ]
    
    # Filter by tags
    if tags:
        tag_list = [t.strip() for t in tags.split(",")]
        transactions = [
            t for t in transactions
            if any(tag in t.get("tags", []) for tag in tag_list)
        ]
    
    # Sort by date descending
    transactions.sort(key=lambda t: t.get("date", ""), reverse=True)
    
    # Paginate
    return {
        "total": len(transactions),
        "skip": skip,
        "limit": limit,
        "transactions": transactions[skip:skip + limit]
    }


@app.get("/transactions/unknown")
async def get_unknown_transactions(skip: int = Query(0), limit: int = Query(100)):
    """Get transactions with unknown/missing categories or marked as Unidentified/Other Expenses."""
    transactions = storage.get_transactions()
    unknown = [
        t for t in transactions 
        if not t.get("category_path") 
        or t.get("category_path") == "Unidentified Expenses"
        or t.get("category_path") == "Other Expenses"
        or "Unidentified" in t.get("category_path", "")
        or "Other Expenses" in t.get("category_path", "")
    ]
    
    unknown.sort(key=lambda t: t.get("date", ""), reverse=True)
    
    return {
        "total": len(unknown),
        "skip": skip,
        "limit": limit,
        "transactions": unknown[skip:skip + limit]
    }


@app.get("/transactions/{transaction_id}")
async def get_transaction(transaction_id: str):
    """Get a specific transaction."""
    transaction = storage.get_transaction(transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction


@app.post("/transactions")
async def create_transaction(req: CreateTransactionRequest):
    """Create a new transaction (traditional way with all fields)."""
    transaction_data = {
        "date": req.date.isoformat(),
        "description": req.description,
        "amount": float(req.amount),
        "currency": req.currency,
        "category_path": req.category_path,
        "merchant": req.merchant,
        "tags": req.tags,
        "transaction_type": req.transaction_type.value,
        "notes": req.notes,
        "source": "manual"
    }
    
    result = storage.create_transaction(transaction_data)
    return result


@app.post("/transactions/smart")
async def create_smart_transaction(description: str, amount: str):
    """
    Create a transaction with AI assistance - just give description and amount!
    AI will figure out: date, merchant, category, proper formatting, etc.
    AI will also create categories if they don't exist.
    
    Example: description="chow", amount="1500" → AI creates proper transaction
    """
    print(f"\n=== SMART TRANSACTION DEBUG ===")
    print(f"Description: {description}")
    print(f"Amount: {amount}")
    try:
        # Get existing categories for AI context
        categories_tree = storage.get_categories()
        print(f"Categories structure type: {type(categories_tree)}")
        print(f"Categories keys: {categories_tree.keys() if isinstance(categories_tree, dict) else 'not a dict'}")
        categories_list = _extract_category_paths(categories_tree)
        print(f"Extracted {len(categories_list)} category paths: {categories_list}")
        
        # Check merchant dictionary for learned preferences
        learned_category = None
        merchant = storage.get_merchant_by_name(description.strip())
        if merchant and merchant.get("preferred_category"):
            learned_category = merchant["preferred_category"]
            print(f"Found learned preference: '{description}' -> '{learned_category}'")
        
        # Let AI parse and enrich the input
        categories_context = f"\n\nEXISTING CATEGORIES (use these first, avoid duplicates):\n{chr(10).join('- ' + cat for cat in categories_list)}" if categories_list else "\n\nNo categories exist yet."
        
        learned_context = f"\n\nLEARNED PREFERENCE: This merchant should be categorized as '{learned_category}'" if learned_category else ""
        
        prompt = f"""Transaction to parse:
Description: {description}
Amount: {amount}
{categories_context}{learned_context}

IMPORTANT: If a matching category exists, use it EXACTLY as written. If there's a learned preference, USE IT. Only suggest a new category name if none of the existing ones are suitable.

Create JSON with:
- date: YYYY-MM-DD (default: {datetime.now().strftime('%Y-%m-%d')})
- merchant: cleaned merchant name
- amount: numeric value (e.g., 15.00)
- description: cleaned description
- suggested_category: EXACT match from existing categories OR new category name

Examples:
- "chow 1500" with existing "Food & Dining" → use "Food & Dining"
- "petrol 5000" with existing "Transportation" → use "Transportation"  
- "groceries 8500" with NO food category → suggest "Groceries"

JSON only:"""
        
        print("Calling AI to parse transaction...")
        response = await ai_service._call_ollama(prompt)
        print(f"AI response length: {len(response)}")
        print(f"AI response: {response}")
        
        # Parse AI response
        import re
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            parsed = json.loads(json_match.group())
        else:
            # Fallback: create basic transaction
            parsed = {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "merchant": description,
                "amount": float(re.sub(r'[^0-9.]', '', amount)),
                "description": description,
                "suggested_category": None
            }
        
        # Handle category - prioritize learned preference over AI suggestion
        category_path = None
        
        # First priority: Use learned preference if we have one
        if learned_category and learned_category in categories_list:
            category_path = learned_category
            print(f"Using learned category: {learned_category}")
        else:
            # Second priority: Use AI's suggestion
            suggested_cat = parsed.get("suggested_category")
            
            if suggested_cat and suggested_cat not in categories_list:
                # AI suggested a new category - create it!
                try:
                    category_data = {
                        "name": suggested_cat,
                        "parent_id": None,  # Top-level category
                        "icon": "📁",
                        "color": "#4A90E2",
                        "description": f"Auto-created by AI",
                        "children": []
                    }
                    storage.create_category(category_data)
                    category_path = suggested_cat
                except Exception:
                    # Category creation failed, leave uncategorized
                    category_path = None
            elif suggested_cat in categories_list:
                # Category exists
                category_path = suggested_cat
        
        # Create transaction (merchant not stored, only used by AI for categorization)
        merchant_hint = parsed.get("merchant", description)  # AI uses this but we don't store it
        transaction_data = {
            "date": parsed.get("date", datetime.now().strftime("%Y-%m-%d")),
            "description": parsed.get("description", description),
            "amount": float(parsed.get("amount", amount)),
            "currency": "ZAR",  # South African Rand
            "category_path": category_path,
            "merchant": None,  # Don't store merchant
            "tags": ["smart_entry"],
            "transaction_type": TransactionType.EXPENSE.value,
            "notes": f"AI suggested: {category_path} (from: {merchant_hint})" if category_path else "AI processing",
            "source": "smart_entry"
        }
        
        result = storage.create_transaction(transaction_data)
        
        return {
            "transaction": result,
            "ai_suggestion": category_path,
            "category_created": suggested_cat not in categories_list if suggested_cat else False,
            "message": f"Transaction created and categorized as '{category_path}'!" if category_path else "Transaction created!"
        }
        
    except Exception as e:
        print(f"ERROR in smart transaction: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"Failed to create transaction: {str(e)}")


def _extract_category_paths(tree_data, prefix=""):
    """Extract all category paths from tree recursively."""
    paths = []
    
    # Handle dict with "nodes" key (the actual storage format)
    if isinstance(tree_data, dict) and "nodes" in tree_data:
        nodes = tree_data["nodes"]
        print(f"Processing {len(nodes)} nodes")
        # Get all root nodes (parent_id is None)
        for node_id, node in nodes.items():
            if node.get("parent_id") is None:
                path = node["name"]
                paths.append(path)
                # Add children recursively
                if node.get("children"):
                    for child_id in node["children"]:
                        if child_id in nodes:
                            child_paths = _build_child_paths(nodes, child_id, path)
                            paths.extend(child_paths)
    # Handle list format (if ever used)
    elif isinstance(tree_data, list):
        for node in tree_data:
            path = f"{prefix}/{node['name']}" if prefix else node['name']
            paths.append(path)
            if node.get('children'):
                paths.extend(_extract_category_paths(node['children'], path))
    
    return paths


def _build_child_paths(nodes, node_id, parent_path):
    """Recursively build child category paths."""
    paths = []
    if node_id in nodes:
        node = nodes[node_id]
        path = f"{parent_path}/{node['name']}"
        paths.append(path)
        if node.get("children"):
            for child_id in node["children"]:
                child_paths = _build_child_paths(nodes, child_id, path)
                paths.extend(child_paths)
    return paths


@app.patch("/transactions/{transaction_id}")
async def update_transaction(transaction_id: str, req: UpdateTransactionRequest):
    """Update a transaction. When category is changed, learn the merchant-category mapping."""
    print(f"\n=== UPDATE TRANSACTION DEBUG ===")
    print(f"Transaction ID: {transaction_id}")
    
    # Get the original transaction
    original = storage.get_transaction(transaction_id)
    if not original:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    updates = {}
    if req.date:
        updates["date"] = req.date.isoformat()
    if req.description:
        updates["description"] = req.description
    if req.amount:
        updates["amount"] = float(req.amount)
    if req.category_path is not None:
        updates["category_path"] = req.category_path
        
        # LEARN: When user manually changes category, save this knowledge
        description = req.description or original.get("description", "")
        if description and req.category_path:
            print(f"Learning: '{description}' -> '{req.category_path}'")
            _learn_merchant_category(description, req.category_path)
    
    if req.merchant:
        updates["merchant"] = req.merchant
    if req.tags:
        updates["tags"] = req.tags
    if req.notes:
        updates["notes"] = req.notes
    
    try:
        result = storage.update_transaction(transaction_id, updates)
        return result
    except Exception as e:
        print(f"ERROR updating transaction: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))


def _learn_merchant_category(description: str, category_path: str):
    """Learn that a merchant/description should be categorized a certain way."""
    try:
        # Normalize the description (lowercase, clean)
        merchant_name = description.strip().lower()
        
        # Check if merchant already exists
        merchant = storage.get_merchant_by_name(merchant_name)
        
        if merchant:
            # Update existing merchant's category preference
            print(f"Updating existing merchant: {merchant['name']}")
            storage.update_merchant(merchant["id"], {
                "preferred_category": category_path
            })
        else:
            # Create new merchant entry
            print(f"Creating new merchant: {merchant_name}")
            merchant_data = {
                "name": merchant_name,
                "preferred_category": category_path,
                "aliases": [merchant_name],
                "confidence": 1.0
            }
            storage.create_merchant(merchant_data)
        
        print(f"✓ Learned: '{merchant_name}' should be categorized as '{category_path}'")
    except Exception as e:
        print(f"Warning: Failed to learn merchant mapping: {e}")
        import traceback
        traceback.print_exc()
        # Don't fail the transaction update if learning fails


@app.delete("/transactions/{transaction_id}")
async def delete_transaction(transaction_id: str):
    """Delete a transaction."""
    print(f"\n=== DELETE TRANSACTION DEBUG ===")
    print(f"Transaction ID: {transaction_id}")
    try:
        storage.delete_transaction(transaction_id)
        print(f"Transaction {transaction_id} deleted successfully")
        return {"status": "deleted", "id": transaction_id}
    except Exception as e:
        print(f"ERROR deleting transaction: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))


# ============ CATEGORIES ============

@app.get("/categories")
async def get_categories():
    """Get the category tree."""
    return storage.get_categories()


@app.post("/categories")
async def create_category(req: CreateCategoryRequest):
    """Create a new category."""
    # If parent_id is provided as a name, look up the actual ID
    parent_id = req.parent_id
    if parent_id:
        categories = storage.get_categories()
        # Check if parent_id is a name instead of an ID
        if parent_id not in categories.get("nodes", {}):
            # It's a name, find the ID
            for node_id, node in categories["nodes"].items():
                if node["name"] == parent_id:
                    parent_id = node_id
                    print(f"Resolved parent '{req.parent_id}' to ID: {parent_id}")
                    break
    
    category_data = {
        "name": req.name,
        "parent_id": parent_id,
        "icon": req.icon,
        "color": req.color,
        "description": req.description,
        "children": []
    }
    
    result = storage.create_category(category_data)
    return result


@app.put("/categories")
async def update_categories(tree: CategoryTree):
    """Replace the entire category tree."""
    storage.update_categories(tree.model_dump())
    return storage.get_categories()


@app.patch("/categories/{category_id}")
async def update_category(category_id: str, updates: Dict[str, Any]):
    """Update a single category (e.g., move to new parent)."""
    try:
        categories = storage.get_categories()
        nodes = categories.get("nodes", {})
        
        if category_id not in nodes:
            raise HTTPException(status_code=404, detail="Category not found")
        
        node = nodes[category_id]
        old_parent_id = node.get("parent_id")
        new_parent_id = updates.get("parent_id")
        
        # Update parent_id
        if "parent_id" in updates:
            # Remove from old parent's children
            if old_parent_id and old_parent_id in nodes:
                old_parent = nodes[old_parent_id]
                if category_id in old_parent.get("children", []):
                    old_parent["children"].remove(category_id)
            elif old_parent_id is None:
                # Remove from root_ids
                if category_id in categories.get("root_ids", []):
                    categories["root_ids"].remove(category_id)
            
            # Add to new parent's children
            if new_parent_id and new_parent_id in nodes:
                new_parent = nodes[new_parent_id]
                if "children" not in new_parent:
                    new_parent["children"] = []
                if category_id not in new_parent["children"]:
                    new_parent["children"].append(category_id)
            elif new_parent_id is None:
                # Add to root_ids
                if "root_ids" not in categories:
                    categories["root_ids"] = []
                if category_id not in categories["root_ids"]:
                    categories["root_ids"].append(category_id)
            
            # Update the node's parent_id
            node["parent_id"] = new_parent_id
        
        # Update other fields
        for key in ["name", "icon", "color"]:
            if key in updates:
                node[key] = updates[key]
        
        storage.update_categories(categories)
        return storage.get_categories()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/categories/{category_id}")
async def delete_category(category_id: str):
    """Delete a category and move its transactions to unknowns."""
    print(f"\n=== DELETE CATEGORY DEBUG ===")
    print(f"Category ID: {category_id}")
    try:
        # Get category name for matching transactions
        categories = storage.get_categories()
        nodes = categories.get("nodes", {})
        
        if category_id in nodes:
            category_name = nodes[category_id].get("name", "")
            
            # Find all transactions with this category and set to None
            transactions = storage.get_transactions()
            for trans in transactions:
                cat_path = trans.get("category_path", "")
                # Check if transaction uses this category or any subcategory
                if cat_path and (cat_path == category_name or cat_path.startswith(category_name + "/")):
                    storage.update_transaction(trans["id"], {"category_path": None})
                    print(f"Moved transaction {trans['id']} to unknowns")
        
        storage.delete_category(category_id)
        print(f"Category {category_id} deleted successfully")
        return {"status": "deleted", "id": category_id}
    except Exception as e:
        print(f"ERROR deleting category: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))


# Initialize default categories if empty
@app.on_event("startup")
async def init_categories():
    """Initialize default categories if the tree is empty."""
    categories = storage.get_categories()
    if not categories.get("nodes"):
        default_categories = [
            {
                "name": "Food & Dining",
                "icon": "🍔",
                "color": "#FF6B6B",
                "children": [
                    {"name": "Groceries", "icon": "🥬"},
                    {"name": "Restaurants", "icon": "🍽️"},
                    {"name": "Takeout", "icon": "🍜"},
                ]
            },
            {
                "name": "Transportation",
                "icon": "🚗",
                "color": "#4ECDC4",
                "children": [
                    {"name": "Petrol", "icon": "⛽"},
                    {"name": "Parking", "icon": "🅿️"},
                    {"name": "Public Transit", "icon": "🚌"},
                ]
            },
            {
                "name": "Utilities",
                "icon": "⚡",
                "color": "#95E1D3",
                "children": [
                    {"name": "Electricity", "icon": "💡"},
                    {"name": "Water", "icon": "💧"},
                    {"name": "Internet", "icon": "📡"},
                ]
            },
            {
                "name": "Entertainment",
                "icon": "🎬",
                "color": "#F38181",
                "children": [
                    {"name": "Movies", "icon": "🎥"},
                    {"name": "Games", "icon": "🎮"},
                    {"name": "Hobbies", "icon": "🎨"},
                ]
            },
            {
                "name": "Health & Fitness",
                "icon": "💪",
                "color": "#AA96DA",
                "children": [
                    {"name": "Gym", "icon": "🏋️"},
                    {"name": "Medical", "icon": "⚕️"},
                    {"name": "Medications", "icon": "💊"},
                ]
            },
            {
                "name": "Shopping",
                "icon": "🛍️",
                "color": "#FCBAD3",
                "children": [
                    {"name": "Clothing", "icon": "👕"},
                    {"name": "Electronics", "icon": "📱"},
                    {"name": "Books", "icon": "📚"},
                ]
            },
            {
                "name": "Income",
                "icon": "💰",
                "color": "#A8E6CF",
                "children": [
                    {"name": "Salary", "icon": "💼"},
                    {"name": "Freelance", "icon": "💻"},
                    {"name": "Investments", "icon": "📈"},
                ]
            }
        ]
        
        # Build category tree recursively
        category_tree = {"nodes": {}, "root_ids": []}
        
        def add_categories(items, parent_id=None):
            for item in items:
                cat_id = item.get("name").lower().replace(" ", "_")
                cat_node = {
                    "id": cat_id,
                    "name": item["name"],
                    "parent_id": parent_id,
                    "icon": item.get("icon"),
                    "color": item.get("color"),
                    "children": []
                }
                category_tree["nodes"][cat_id] = cat_node
                
                if parent_id is None:
                    category_tree["root_ids"].append(cat_id)
                else:
                    if cat_id not in category_tree["nodes"][parent_id]["children"]:
                        category_tree["nodes"][parent_id]["children"].append(cat_id)
                
                # Recursively add children
                if "children" in item:
                    add_categories(item["children"], cat_id)
        
        add_categories(default_categories)
        storage.update_categories(category_tree)


# ============ BUDGETS ============

@app.get("/budgets")
async def list_budgets():
    """List all budgets."""
    budgets = storage.get_budgets()
    return {"budgets": budgets}


@app.post("/budgets")
async def create_budget(req: CreateBudgetRequest):
    """Create a new budget with hierarchical validation."""
    # Validate against parent budgets
    if req.category_path:
        existing_budgets = storage.get_budgets()
        
        # Find parent budgets (categories that this category is under)
        path_parts = req.category_path.split('/')
        for i in range(len(path_parts) - 1):
            parent_path = '/'.join(path_parts[:i+1])
            
            # Check if parent has a budget
            parent_budgets = [b for b in existing_budgets 
                            if b.get('category_path') == parent_path 
                            and b.get('period') == req.period]
            
            if parent_budgets:
                parent_budget = parent_budgets[0]
                parent_amount = Decimal(str(parent_budget.get('amount', 0)))
                
                if req.amount > parent_amount:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Budget amount (R{float(req.amount):,.2f}) cannot exceed parent category '{parent_path}' budget (R{float(parent_amount):,.2f})"
                    )
        
        # Check if subcategory budgets would exceed this budget
        subcategory_budgets = [b for b in existing_budgets 
                              if b.get('category_path', '').startswith(req.category_path + '/')
                              and b.get('period') == req.period]
        
        if subcategory_budgets:
            max_sub_budget = max(Decimal(str(b.get('amount', 0))) for b in subcategory_budgets)
            if req.amount < max_sub_budget:
                raise HTTPException(
                    status_code=400,
                    detail=f"Budget amount (R{float(req.amount):,.2f}) cannot be less than existing subcategory budgets (max: R{float(max_sub_budget):,.2f})"
                )
    
    budget_data = {
        "category_path": req.category_path,
        "amount": float(req.amount),
        "period": req.period,
        "start_date": req.start_date.isoformat(),
        "end_date": req.end_date.isoformat() if req.end_date else None,
        "tags_filter": req.tags_filter,
        "notes": req.notes
    }
    
    result = storage.create_budget(budget_data)
    return result


@app.get("/budgets/status")
async def get_budget_status():
    """Get status of all budgets with current spending."""
    budgets = storage.get_budgets()
    transactions = storage.get_transactions()
    statuses = []
    
    for budget in budgets:
        # Filter transactions for this budget
        category_path = budget.get("category_path")
        filtered_transactions = transactions
        
        if category_path:
            filtered_transactions = [
                t for t in filtered_transactions
                if t.get("category_path") and t.get("category_path").startswith(category_path)
            ]
        
        # Filter by tags if specified
        if budget.get("tags_filter"):
            filtered_transactions = [
                t for t in filtered_transactions
                if any(tag in t.get("tags", []) for tag in budget["tags_filter"])
            ]
        
        # Sum spending
        spent = sum(
            Decimal(str(t.get("amount", 0)))
            for t in filtered_transactions
            if t.get("transaction_type") == TransactionType.EXPENSE.value
        )
        
        budget_amount = Decimal(str(budget.get("amount", 0)))
        percentage = float(spent / budget_amount * 100) if budget_amount > 0 else 0
        
        # Determine status
        if percentage >= 100:
            status = BudgetStatus.EXCEEDED
        elif percentage >= 75:
            status = BudgetStatus.APPROACHING
        else:
            status = BudgetStatus.OK
        
        statuses.append({
            "budget_id": budget.get("id"),
            "category_path": category_path,
            "period": budget.get("period"),
            "budget_amount": float(budget_amount),
            "spent_amount": float(spent),
            "percentage": percentage,
            "status": status.value,
            "remaining": float(budget_amount - spent)
        })
    
    return {"statuses": statuses}


@app.get("/budgets/{budget_id}")
async def get_budget(budget_id: str):
    """Get a specific budget."""
    budgets = storage.get_budgets()
    budget = next((b for b in budgets if b.get("id") == budget_id), None)
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    return budget


@app.delete("/budgets/{budget_id}")
async def delete_budget(budget_id: str):
    """Delete a budget."""
    try:
        storage.delete_budget(budget_id)
        return {"status": "deleted"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/budgets/{budget_id}")
async def update_budget(budget_id: str, updates: Dict[str, Any]):
    """Update an existing budget with partial data."""
    try:
        # Get existing budget
        existing = storage.get_budget(budget_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Budget not found")
        
        # Update only provided fields
        storage.update_budget(budget_id, updates)
        return storage.get_budget(budget_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============ MERCHANTS ============

@app.get("/merchants")
async def list_merchants():
    """List all merchants."""
    merchants = storage.get_merchants()
    return {"merchants": list(merchants.values())}


@app.post("/merchants")
async def create_merchant(merchant: Dict[str, Any]):
    """Create a new merchant."""
    merchant_data = {
        "name": merchant.get("name"),
        "aliases": merchant.get("aliases", []),
        "default_category": merchant.get("default_category"),
        "patterns": merchant.get("patterns", []),
        "confidence": merchant.get("confidence", 1.0),
        "notes": merchant.get("notes")
    }
    
    result = storage.create_merchant(merchant_data)
    return result


@app.get("/merchants/{merchant_id}")
async def get_merchant(merchant_id: str):
    """Get a specific merchant."""
    merchants = storage.get_merchants()
    if merchant_id not in merchants:
        raise HTTPException(status_code=404, detail="Merchant not found")
    return merchants[merchant_id]


@app.patch("/merchants/{merchant_id}")
async def update_merchant(merchant_id: str, updates: Dict[str, Any]):
    """Update a merchant."""
    try:
        result = storage.update_merchant(merchant_id, updates)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/merchants/{merchant_id}")
async def delete_merchant(merchant_id: str):
    """Delete a merchant."""
    try:
        storage.delete_merchant(merchant_id)
        return {"status": "deleted"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============ IMPORTS ============

@app.post("/imports/bank-csv")
async def import_bank_csv(req: BankImportRequest):
    """Import transactions from bank CSV."""
    print("\n=== CSV IMPORT DEBUG ===")
    try:
        # Parse CSV content - handle bank CSVs with metadata rows
        lines = req.file_content.strip().split('\n')
        
        # Find the header row (look for common column names)
        header_keywords = ['date', 'description', 'amount', 'debit', 'credit', 'balance', 'posting', 'transaction']
        header_row_idx = 0
        
        for i, line in enumerate(lines[:10]):  # Check first 10 rows
            lower_line = line.lower()
            matches = sum(1 for keyword in header_keywords if keyword in lower_line)
            if matches >= 3:  # Found a row with at least 3 column keywords
                header_row_idx = i
                print(f"Found header row at line {i}: {line[:100]}")
                break
        
        # Reconstruct CSV starting from header row
        csv_content = '\n'.join(lines[header_row_idx:])
        csv_reader = csv.DictReader(io.StringIO(csv_content))
        
        imported_count = 0
        duplicate_count = 0
        skipped_count = 0
        row_number = 0
        
        # Log columns found
        first_row = None
        
        for row in csv_reader:
            row_number += 1
            
            # Log first row for debugging
            if row_number == 1:
                first_row = row
                print(f"CSV Columns found: {list(row.keys())}")
                print(f"First row sample: {dict(list(row.items())[:5])}")
            
            # Parse based on format - try multiple common column names
            date_str = None
            for key in row.keys():
                if key and any(x in key.lower() for x in ['transaction date', 'trans date', 'posting date', 'date']):
                    date_str = row[key]
                    break
            
            description = None
            for key in row.keys():
                if key and any(x in key.lower() for x in ['description', 'memo', 'details', 'narration', 'reference']):
                    description = row[key]
                    break
            
            # Try to find amount, debit, or credit columns
            amount_str = None
            for key in row.keys():
                if key and 'amount' in key.lower():
                    amount_str = row[key]
                    break
            
            # Try debit/credit columns if Amount not found
            if not amount_str:
                debit = None
                credit = None
                for key in row.keys():
                    key_lower = (key or '').lower()
                    if 'debit' in key_lower or 'withdrawal' in key_lower:
                        debit = row[key]
                    elif 'credit' in key_lower or 'deposit' in key_lower:
                        credit = row[key]
                
                # Debit = money out (negative), Credit = money in (positive)
                if debit and debit.strip() and debit.strip() not in ['0', '0.00', '', '-']:
                    amount_str = f"-{debit}"
                elif credit and credit.strip() and credit.strip() not in ['0', '0.00', '', '-']:
                    amount_str = credit
            
            if not all([date_str, amount_str]):
                if row_number <= 3:
                    print(f"Row {row_number} skipped - missing data. Date: '{date_str}', Amount: '{amount_str}', Desc: '{description}'")
                skipped_count += 1
                continue
            
            # Parse amount (handle negative values)
            try:
                # Remove common currency symbols and thousands separators
                clean_amount = amount_str.replace(",", "").replace("$", "").replace("R", "").replace(" ", "").strip()
                # Handle parentheses as negative (accounting format)
                if clean_amount.startswith("(") and clean_amount.endswith(")"):
                    clean_amount = "-" + clean_amount[1:-1]
                amount = Decimal(clean_amount)
                
                if row_number <= 3:
                    print(f"Row {row_number} parsed - Amount: {amount}, Date: {date_str}, Desc: {description[:50] if description else 'N/A'}")
            except Exception as parse_error:
                if row_number <= 3:
                    print(f"Row {row_number} amount parse error: {parse_error} - original: '{amount_str}'")
                skipped_count += 1
                continue
            
            # Skip if amount is 0
            if amount == 0:
                skipped_count += 1
                continue
            
            # Parse date
            try:
                from dateutil import parser
                date = parser.parse(date_str)
            except Exception as date_error:
                if row_number <= 3:
                    print(f"Row {row_number} date parse error: {date_error} - original: '{date_str}'")
                skipped_count += 1
                continue
            
            # Determine transaction type (negative = expense, positive = income)
            is_expense = amount < 0
            abs_amount = float(abs(amount))
            
            # Check for duplicates using date, description, and amount
            existing = [t for t in storage.get_transactions() 
                       if t.get("date", "").startswith(date.date().isoformat()) and
                       t.get("description") == description and
                       abs(t.get("amount", 0) - abs_amount) < 0.01]
            
            if existing:
                duplicate_count += 1
                continue
            
            # Create transaction with ZAR currency
            transaction_data = {
                "date": date.isoformat(),
                "description": description or "Bank Transaction",
                "amount": abs_amount,
                "currency": "ZAR",
                "category_path": None,
                "merchant": description or "Unknown",
                "tags": ["imported"],
                "transaction_type": TransactionType.EXPENSE.value if is_expense else TransactionType.INCOME.value,
                "source": f"bank_import_{req.bank_format}"
            }
            
            created = storage.create_transaction(transaction_data)
            imported_count += 1
        
        print(f"\n=== CSV IMPORT SUMMARY ===")
        print(f"Total rows processed: {row_number}")
        print(f"Imported: {imported_count}")
        print(f"Duplicates: {duplicate_count}")
        print(f"Skipped: {skipped_count}")
        
        # Batch AI categorization for all imported transactions
        if imported_count > 0:
            try:
                print(f"Running AI categorization for {imported_count} transactions...")
                categories = storage.get_categories()
                uncategorized = [t for t in storage.get_transactions() 
                                if not t.get('category_path') and t.get('tags') and 'imported' in t.get('tags', [])]
                
                if uncategorized:
                    # Process in batches to avoid overwhelming AI
                    batch_size = 50
                    total_categorized = 0
                    
                    for i in range(0, len(uncategorized[:imported_count]), batch_size):
                        batch = uncategorized[i:i+batch_size]
                        print(f"Processing batch {i//batch_size + 1}/{(len(uncategorized[:imported_count]) + batch_size - 1)//batch_size}...")
                        
                        categorized = await ai_service.categorise_transactions(batch, categories)
                        for trans in categorized:
                            if trans.get('category_path') and trans.get('id'):
                                storage.update_transaction(trans['id'], {
                                    'category_path': trans['category_path']
                                })
                                total_categorized += 1
                    
                    print(f"AI categorization complete: {total_categorized} transactions categorized")
            except Exception as ai_error:
                print(f"Batch AI categorization failed: {ai_error}")
                import traceback
                traceback.print_exc()
        
        return {
            "status": "success",
            "imported": imported_count,
            "duplicates": duplicate_count
        }
    except Exception as e:
        import traceback
        print(f"CSV Import Error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"Import failed: {str(e)}")


# ============ RECONCILIATION ============

@app.get("/reconciliation")
async def get_reconciliation_candidates():
    """Get potential reconciliation matches between bank statements and receipts."""
    transactions = storage.get_transactions()
    
    # Simple matching by amount and date proximity
    matches = []
    
    # Group transactions by amount
    by_amount = {}
    for t in transactions:
        amount = t.get("amount")
        if amount not in by_amount:
            by_amount[amount] = []
        by_amount[amount].append(t)
    
    # Find potential duplicates (same amount within 1 day)
    for amount, trans_list in by_amount.items():
        if len(trans_list) > 1:
            for i, t1 in enumerate(trans_list):
                for t2 in trans_list[i+1:]:
                    date1 = datetime.fromisoformat(t1.get("date", ""))
                    date2 = datetime.fromisoformat(t2.get("date", ""))
                    
                    if abs((date1 - date2).days) <= 1:
                        match = {
                            "id": f"{t1.get('id')}_{t2.get('id')}",
                            "transaction_id": t1.get("id"),
                            "receipt_id": t2.get("id"),
                            "confidence": 0.8,
                            "match_reason": f"amount_date_match: ${amount}",
                            "is_confirmed": False
                        }
                        matches.append(match)
    
    return {
        "matches": matches
    }


# ============ AI ENRICHMENT ============

@app.post("/ai/categorise")
async def ai_categorise_transactions():
    """Use AI to suggest categories for uncategorized transactions."""
    try:
        transactions = storage.get_transactions()
        unknown = [t for t in transactions if not t.get("category_path")]
        
        if not unknown:
            return {"categorised": 0, "transactions": []}
        
        categories = storage.get_categories()
        
        # Call AI service to categorize
        categorised = await ai_service.categorise_transactions(unknown, categories)
        
        # Update transactions that were categorized by AI
        updated_count = 0
        for trans in categorised:
            if trans.get("category_path") and not any(t.get("id") == trans.get("id") for t in unknown if t.get("category_path")):
                # This transaction was categorized by AI
                try:
                    storage.update_transaction(trans.get("id"), {
                        "category_path": trans.get("category_path")
                    })
                    updated_count += 1
                except:
                    pass
        
        return {
            "categorised": updated_count,
            "total_processed": len(unknown),
            "transactions": categorised[:10]  # Return first 10
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"AI categorization failed: {str(e)}")


@app.post("/ai/enrich-merchant")
async def ai_enrich_merchant(merchant_name: str, description: str):
    """Use AI to enrich merchant information."""
    try:
        enrichment = await ai_service.enrich_merchant(merchant_name, description)
        return {
            "merchant_name": merchant_name,
            "aliases": enrichment.get("aliases", []),
            "suggested_category": enrichment.get("suggested_category"),
            "confidence": 0.75
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Merchant enrichment failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
