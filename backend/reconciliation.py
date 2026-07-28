"""
Smart reconciliation and duplicate detection for transactions.
Matches receipts to bank statements and detects duplicates across sources.
"""
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
import re


class ReconciliationService:
    """Service for matching and deduplicating transactions."""
    
    def __init__(self, storage):
        """
        Initialize reconciliation service.
        
        Args:
            storage: Storage instance for accessing transactions
        """
        self.storage = storage
    
    def find_duplicates(
        self,
        new_transaction: Dict[str, Any],
        date_tolerance_days: int = 3,
        amount_tolerance_percent: float = 0.01
    ) -> List[Tuple[Dict[str, Any], float]]:
        """
        Find potential duplicate transactions for a new transaction.
        
        Args:
            new_transaction: The transaction to check
            date_tolerance_days: How many days to search +/- from date
            amount_tolerance_percent: Percentage difference allowed in amount (0.01 = 1%)
            
        Returns:
            List of (transaction, confidence_score) tuples, sorted by confidence (highest first)
        """
        # Parse new transaction details
        try:
            new_date = datetime.fromisoformat(new_transaction["date"].replace("Z", "+00:00"))
        except:
            new_date = datetime.now()
        
        new_amount = Decimal(str(new_transaction.get("amount", 0)))
        new_merchant = self._normalize_merchant(new_transaction.get("merchant", ""))
        new_description = self._normalize_text(new_transaction.get("description", ""))
        
        # Get all existing transactions
        all_transactions = self.storage.list_transactions()
        
        matches = []
        
        for existing in all_transactions:
            # Skip if same ID
            if existing.get("id") == new_transaction.get("id"):
                continue
            
            confidence = self._calculate_match_confidence(
                new_date=new_date,
                new_amount=new_amount,
                new_merchant=new_merchant,
                new_description=new_description,
                existing=existing,
                date_tolerance_days=date_tolerance_days,
                amount_tolerance_percent=amount_tolerance_percent
            )
            
            if confidence > 0.5:  # Only include matches above 50% confidence
                matches.append((existing, confidence))
        
        # Sort by confidence (highest first)
        matches.sort(key=lambda x: x[1], reverse=True)
        
        return matches
    
    def check_month_statement_exists(
        self,
        year: int,
        month: int,
        source_pattern: str = "statement"
    ) -> bool:
        """
        Check if a bank statement for a given month already exists.
        
        Args:
            year: Year to check
            month: Month to check (1-12)
            source_pattern: Pattern to match in transaction source field
            
        Returns:
            True if statement exists for this month
        """
        all_transactions = self.storage.list_transactions()
        
        for trans in all_transactions:
            # Check source
            source = trans.get("source", "")
            if source_pattern not in source.lower():
                continue
            
            # Check date
            try:
                trans_date = datetime.fromisoformat(trans["date"].replace("Z", "+00:00"))
                if trans_date.year == year and trans_date.month == month:
                    return True
            except:
                continue
        
        return False
    
    def find_statement_transaction(
        self,
        receipt_transaction: Dict[str, Any],
        year: int,
        month: int
    ) -> Optional[Dict[str, Any]]:
        """
        Find a matching bank statement transaction for a receipt.
        
        Args:
            receipt_transaction: The receipt transaction to match
            year: Year of bank statement
            month: Month of bank statement
            
        Returns:
            Matching statement transaction or None
        """
        try:
            receipt_date = datetime.fromisoformat(receipt_transaction["date"].replace("Z", "+00:00"))
        except:
            receipt_date = datetime.now()
        
        receipt_amount = Decimal(str(receipt_transaction.get("amount", 0)))
        receipt_merchant = self._normalize_merchant(receipt_transaction.get("merchant", ""))
        
        # Get all statement transactions for this month
        all_transactions = self.storage.list_transactions()
        
        candidates = []
        
        for trans in all_transactions:
            # Must be from statement
            if "statement" not in trans.get("source", "").lower():
                continue
            
            # Must be in same month
            try:
                trans_date = datetime.fromisoformat(trans["date"].replace("Z", "+00:00"))
                if trans_date.year != year or trans_date.month != month:
                    continue
            except:
                continue
            
            # Calculate match confidence
            confidence = self._calculate_match_confidence(
                new_date=receipt_date,
                new_amount=receipt_amount,
                new_merchant=receipt_merchant,
                new_description=self._normalize_text(receipt_transaction.get("description", "")),
                existing=trans,
                date_tolerance_days=5,
                amount_tolerance_percent=0.01
            )
            
            if confidence > 0.7:  # Higher threshold for statement matching
                candidates.append((trans, confidence))
        
        if candidates:
            # Return best match
            candidates.sort(key=lambda x: x[1], reverse=True)
            return candidates[0][0]
        
        return None
    
    def _calculate_match_confidence(
        self,
        new_date: datetime,
        new_amount: Decimal,
        new_merchant: str,
        new_description: str,
        existing: Dict[str, Any],
        date_tolerance_days: int,
        amount_tolerance_percent: float
    ) -> float:
        """
        Calculate confidence score (0-1) that two transactions are duplicates.
        
        Scoring:
        - Amount match: 40% weight
        - Date proximity: 30% weight
        - Merchant/description similarity: 30% weight
        """
        confidence = 0.0
        
        # Parse existing transaction
        try:
            existing_date = datetime.fromisoformat(existing["date"].replace("Z", "+00:00"))
        except:
            return 0.0
        
        existing_amount = Decimal(str(existing.get("amount", 0)))
        existing_merchant = self._normalize_merchant(existing.get("merchant", ""))
        existing_description = self._normalize_text(existing.get("description", ""))
        
        # 1. Amount match (40%)
        if new_amount == existing_amount:
            confidence += 0.4
        else:
            amount_diff = abs(new_amount - existing_amount)
            tolerance = existing_amount * Decimal(str(amount_tolerance_percent))
            if amount_diff <= tolerance:
                confidence += 0.4 * (1 - float(amount_diff / tolerance))
        
        # 2. Date proximity (30%)
        date_diff = abs((new_date - existing_date).days)
        if date_diff == 0:
            confidence += 0.3
        elif date_diff <= date_tolerance_days:
            confidence += 0.3 * (1 - (date_diff / date_tolerance_days))
        
        # 3. Merchant/description similarity (30%)
        text_similarity = self._text_similarity(
            new_merchant + " " + new_description,
            existing_merchant + " " + existing_description
        )
        confidence += 0.3 * text_similarity
        
        return confidence
    
    def _normalize_merchant(self, merchant: str) -> str:
        """Normalize merchant name for comparison."""
        if not merchant:
            return ""
        
        # Convert to lowercase
        merchant = merchant.lower().strip()
        
        # Remove common suffixes/patterns
        patterns_to_remove = [
            r'\s+#\d+',  # Store numbers like " #123"
            r'\s+\d{4,}',  # Long numbers
            r'\s+inc\.?$',  # Inc
            r'\s+llc\.?$',  # LLC
            r'\s+ltd\.?$',  # Ltd
            r'\s+corp\.?$',  # Corp
        ]
        
        for pattern in patterns_to_remove:
            merchant = re.sub(pattern, '', merchant)
        
        return merchant.strip()
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison."""
        if not text:
            return ""
        return text.lower().strip()
    
    def _text_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate simple text similarity (0-1).
        Uses word overlap and substring matching.
        """
        if not text1 or not text2:
            return 0.0
        
        # Normalize
        text1 = text1.lower()
        text2 = text2.lower()
        
        # Check substring
        if text1 in text2 or text2 in text1:
            return 0.9
        
        # Word overlap
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
        
        common_words = words1 & words2
        total_unique_words = len(words1 | words2)
        
        if total_unique_words == 0:
            return 0.0
        
        overlap_score = len(common_words) / total_unique_words
        
        return overlap_score
