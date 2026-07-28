"""
AI service for transaction categorization and merchant enrichment.
Pluggable design to support multiple LLM backends.
"""
from typing import List, Optional, Dict, Any, Tuple
from abc import ABC, abstractmethod
from models import Transaction, Merchant
import httpx
import json
import asyncio
import re
from datetime import datetime
from decimal import Decimal


class AiServiceBase(ABC):
    """Abstract base for AI service implementations."""

    @abstractmethod
    async def categorise_transactions(
        self,
        transactions: List[Dict],
        categories: Dict[str, Any]
    ) -> List[Dict]:
        """
        Suggest categories for uncategorized transactions.
        Returns list of transactions with suggested category_paths.
        """
        pass

    @abstractmethod
    async def enrich_merchant(
        self,
        merchant_name: str,
        description: str
    ) -> Dict[str, Any]:
        """
        Enrich merchant information (aliases, default category).
        Returns dict with 'aliases' and 'suggested_category'.
        """
        pass

    @abstractmethod
    async def classify_document(
        self,
        text: str
    ) -> Dict[str, Any]:
        """
        Classify document type and extract structure.
        Returns dict with:
            - type: 'receipt', 'bank_statement', or 'unknown'
            - confidence: float 0-1
        """
        pass

    @abstractmethod
    async def parse_receipt(
        self,
        text: str
    ) -> Dict[str, Any]:
        """
        Parse receipt text to extract transaction details.
        Returns dict with: date, merchant, amount, items (optional)
        """
        pass

    @abstractmethod
    async def parse_bank_statement(
        self,
        text: str
    ) -> List[Dict[str, Any]]:
        """
        Parse bank statement text to extract transactions.
        Returns list of transactions with: date, description, amount
        """
        pass


class LocalAiService(AiServiceBase):
    """
    Local LLM service via HTTP (e.g., Ollama, LM Studio).
    Ollama runs on localhost:11434 by default.
    Supports both text and vision models (llava for images).
    """

    def __init__(self, server_url: str = "http://localhost:11434", model: str = "mistral", vision_model: str = "llava"):
        self.server_url = server_url
        self.model = model
        self.vision_model = vision_model
        # No timeout for large batch processing

    async def categorise_transactions(
        self,
        transactions: List[Dict],
        categories: Dict[str, Any]
    ) -> List[Dict]:
        """
        Use local LLM to suggest categories for uncategorized transactions.
        Intelligently places subcategories under appropriate parents.
        """
        # Build category hierarchy for context
        nodes = categories.get("nodes", {})
        
        # Create a list of category paths (parent/child format)
        category_paths = []
        for node_id, node in nodes.items():
            name = node.get("name", "")
            parent_id = node.get("parent_id")
            
            if parent_id and parent_id in nodes:
                # Build full path: Parent/Child
                parent_name = nodes[parent_id].get("name", "")
                category_paths.append(f"{parent_name}/{name}")
            else:
                # Root category
                category_paths.append(name)
        
        if not category_paths:
            return transactions
        
        categories_str = "\n".join(f"- {path}" for path in sorted(category_paths))
        
        for trans in transactions:
            if trans.get("category_path"):
                continue  # Already categorized
            
            description = trans.get("description", "")
            merchant = trans.get("merchant", "")
            amount = trans.get("amount", 0)
            
            prompt = f"""You are a South African financial categorization expert. Given a transaction, respond with the MOST SPECIFIC matching category from the hierarchy.

IMPORTANT RULES:
1. Use the full path format "Parent/Child" for subcategories (e.g., "Medical/Prescriptions", "Transport/Petrol")
2. Only use the parent category if no specific subcategory matches
3. Match common South African merchants and terminology

Available categories (use exact format):
{categories_str}

Transaction:
- Description: {description}
- Merchant: {merchant}
- Amount: R{amount}

Respond with ONLY the category path, nothing else."""
            
            try:
                response = await self._call_ollama(prompt)
                category_path = response.strip()
                
                # Validate category exists (check both full paths and individual names)
                if category_path in category_paths:
                    trans["category_path"] = category_path
                    trans["ai_confidence"] = 0.85
                elif "/" not in category_path and category_path in [p.split("/")[0] for p in category_paths]:
                    # Root category match
                    trans["category_path"] = category_path
                    trans["ai_confidence"] = 0.75
            except Exception as e:
                print(f"AI categorization error for '{description}': {e}")
                continue
        
        return transactions

    async def enrich_merchant(
        self,
        merchant_name: str,
        description: str
    ) -> Dict[str, Any]:
        """
        Use local LLM to enrich merchant information (aliases, category hints).
        """
        prompt = f"""You are a financial data enrichment expert. Given a merchant name and description, suggest:
1. Common aliases or variations of this merchant name (comma-separated)
2. The most likely spending category

Merchant: {merchant_name}
Description: {description}

Respond in JSON format ONLY:
{{"aliases": ["alias1", "alias2"], "suggested_category": "Category Name"}}"""
        
        try:
            response = await self._call_ollama(prompt)
            
            # Try to parse JSON from response
            try:
                result = json.loads(response)
                return {
                    "aliases": result.get("aliases", []),
                    "suggested_category": result.get("suggested_category")
                }
            except json.JSONDecodeError:
                # If JSON parsing fails, try to extract parts manually
                return {
                    "aliases": [],
                    "suggested_category": None
                }
        except Exception as e:
            print(f"AI enrichment error for '{merchant_name}': {e}")
            return {
                "aliases": [],
                "suggested_category": None
            }

    async def _call_ollama(self, prompt: str, model: Optional[str] = None) -> str:
        """
        Call the Ollama API with a prompt and return the response.
        No timeout for large batch processing.
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.server_url}/api/generate",
                json={
                    "model": model or self.model,
                    "prompt": prompt,
                    "stream": False
                }
            )
            response.raise_for_status()
            data = response.json()
            return data.get("response", "").strip()
    
    async def _call_ollama_vision(self, prompt: str, base64_image: str) -> str:
        """
        Call the Ollama API with vision (image + prompt) and return the response.
        Uses llava or similar vision-capable model.
        """
        print(f"Calling Ollama vision model: {self.vision_model}")
        print(f"Server URL: {self.server_url}")
        print(f"Image size: {len(base64_image)} chars")
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.server_url}/api/generate",
                    json={
                        "model": self.vision_model,
                        "prompt": prompt,
                        "images": [base64_image],
                        "stream": False
                    }
                )
                print(f"Response status: {response.status_code}")
                response.raise_for_status()
                data = response.json()
                return data.get("response", "").strip()
        except httpx.HTTPStatusError as e:
            print(f"HTTP error: {e.response.status_code}")
            print(f"Response body: {e.response.text}")
            if e.response.status_code == 404:
                raise Exception(f"Model '{self.vision_model}' not found. Run: ollama pull {self.vision_model}")
            raise
        except Exception as e:
            print(f"Vision API error: {e}")
            raise
    
    async def analyze_image(self, base64_image: str, prompt: str) -> str:
        """
        Analyze an image using vision model.
        
        Args:
            base64_image: Base64 encoded image
            prompt: What to analyze/extract from the image
            
        Returns:
            AI response describing the image
        """
        return await self._call_ollama_vision(prompt, base64_image)

    async def classify_document(self, text: str) -> Dict[str, Any]:
        """Classify if text is a receipt or bank statement."""
        prompt = f"""You are a document classifier. Analyze the following text and determine if it's a RECEIPT or a BANK_STATEMENT.

Text:
{text[:1000]}

Respond with ONLY one word: RECEIPT or BANK_STATEMENT"""
        
        try:
            response = await self._call_ollama(prompt)
            doc_type = response.strip().upper()
            
            if "RECEIPT" in doc_type:
                return {"type": "receipt", "confidence": 0.9}
            elif "BANK" in doc_type or "STATEMENT" in doc_type:
                return {"type": "bank_statement", "confidence": 0.9}
            else:
                return {"type": "unknown", "confidence": 0.5}
        except Exception as e:
            print(f"Document classification error: {e}")
            return {"type": "unknown", "confidence": 0.0}

    async def parse_receipt(self, text: str) -> Dict[str, Any]:
        """Parse receipt text to extract transaction details."""
        prompt = f"""You are a receipt parser. Extract the following information from this receipt:
- Date (format: YYYY-MM-DD)
- Merchant name
- Total amount (just the number)

Receipt text:
{text}

Respond in JSON format ONLY:
{{"date": "YYYY-MM-DD", "merchant": "name", "amount": 0.00}}"""
        
        try:
            response = await self._call_ollama(prompt)
            result = json.loads(response)
            
            return {
                "date": result.get("date"),
                "merchant": result.get("merchant"),
                "amount": float(result.get("amount", 0)),
                "description": f"Receipt from {result.get('merchant', 'Unknown')}",
                "source": "receipt_ocr"
            }
        except Exception as e:
            print(f"Receipt parsing error: {e}")
            # Fallback: try regex extraction
            return self._fallback_parse_receipt(text)

    async def parse_bank_statement(self, text: str) -> List[Dict[str, Any]]:
        """Parse bank statement text to extract transactions."""
        print(f"Parsing bank statement, text length: {len(text)}")
        prompt = f"""You are a bank statement parser. Extract ALL valid transactions from this statement.

IMPORTANT RULES:
1. Each transaction MUST have: date (YYYY-MM-DD), description (merchant/vendor name), and amount (number)
2. SKIP balance indicators like "Cr", "Dr", "Balance", "Total" - these are NOT transactions
3. SKIP header rows, column labels, and summary lines
4. The description should be the actual merchant/vendor name, not abbreviations like "Cr" or "Dr"
5. Amount should be a single number (positive or negative)

Statement text:
{text}

Respond with a JSON array of valid transactions ONLY:
[{{"date": "YYYY-MM-DD", "description": "Merchant Name", "amount": -125.50}}]"""
        
        try:
            print("Calling AI to parse transactions...")
            response = await self._call_ollama(prompt)
            print(f"AI response length: {len(response)}")
            print(f"AI response preview: {response[:500]}")
            
            # Try to extract JSON array
            import re
            json_match = re.search(r'\[[\s\S]*\]', response)
            if json_match:
                json_str = json_match.group()
                print(f"Found JSON array: {json_str[:200]}...")
                transactions = json.loads(json_str)
            else:
                print("No JSON array found in response")
                transactions = json.loads(response)
            
            print(f"Parsed {len(transactions)} transactions")
            
            # Validate and clean - filter out junk
            result = []
            invalid_descriptions = ['cr', 'dr', 'balance', 'total', 'debit', 'credit']
            for trans in transactions:
                if all(k in trans for k in ["date", "description", "amount"]):
                    desc = str(trans["description"]).strip().lower()
                    # Skip if description is just balance indicators or too short
                    if desc in invalid_descriptions or len(desc) < 3:
                        print(f"Skipping invalid transaction: {trans}")
                        continue
                    
                    result.append({
                        "date": trans["date"],
                        "description": trans["description"],
                        "amount": float(trans["amount"]),
                        "merchant": trans["description"],
                        "source": "statement_ocr"
                    })
            
            return result
        except Exception as e:
            print(f"ERROR parsing bank statement: {e}")
            import traceback
            traceback.print_exc()
            # Fallback: try regex extraction
            print("Falling back to regex parsing...")
            return self._fallback_parse_statement(text)

    def _fallback_parse_receipt(self, text: str) -> Dict[str, Any]:
        """Fallback regex-based receipt parsing."""
        # Try to find date patterns
        date_patterns = [
            r'\d{4}-\d{2}-\d{2}',
            r'\d{2}/\d{2}/\d{4}',
            r'\d{2}-\d{2}-\d{4}'
        ]
        date_found = None
        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                date_found = match.group()
                break
        
        # Try to find amounts
        amount_pattern = r'\$?\s*(\d+\.\d{2})'
        amounts = re.findall(amount_pattern, text)
        amount = float(amounts[-1]) if amounts else 0.0
        
        # First line as merchant
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        merchant = lines[0] if lines else "Unknown Merchant"
        
        return {
            "date": date_found or datetime.now().strftime("%Y-%m-%d"),
            "merchant": merchant,
            "amount": amount,
            "description": f"Receipt from {merchant}",
            "source": "receipt_ocr_fallback"
        }

    def _fallback_parse_statement(self, text: str) -> List[Dict[str, Any]]:
        """Fallback regex-based statement parsing."""
        transactions = []
        lines = text.split('\n')
        
        # Look for lines with date + amount patterns
        transaction_pattern = r'(\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2})\s+(.+?)\s+(\$?\s*-?\d+\.\d{2})'
        
        for line in lines:
            match = re.search(transaction_pattern, line)
            if match:
                date_str, description, amount_str = match.groups()
                try:
                    amount = float(amount_str.replace('$', '').replace(',', '').strip())
                    transactions.append({
                        "date": date_str,
                        "description": description.strip(),
                        "amount": abs(amount),
                        "merchant": description.strip(),
                        "source": "statement_ocr_fallback"
                    })
                except ValueError:
                    continue
        
        return transactions


class RemoteAiService(AiServiceBase):
    """
    Remote LLM service via API (e.g., OpenAI, Anthropic, Google).
    Requires API key in environment.
    """

    def __init__(self, provider: str = "openai", api_key: Optional[str] = None):
        """
        provider: 'openai', 'anthropic', 'gemini', etc.
        api_key: If None, reads from environment (OPENAI_API_KEY, etc.)
        """
        self.provider = provider
        self.api_key = api_key

    async def categorise_transactions(
        self,
        transactions: List[Dict],
        categories: Dict[str, Any]
    ) -> List[Dict]:
        """
        Send transactions to remote LLM for categorization.
        Returns transactions with suggested categories.
        """
        # TODO: Implement actual API call (OpenAI, etc.)
        return transactions

    async def enrich_merchant(
        self,
        merchant_name: str,
        description: str
    ) -> Dict[str, Any]:
        """
        Query remote LLM for merchant enrichment.
        """
        # TODO: Implement actual API call
        return {
            "aliases": [],
            "suggested_category": None
        }

    async def classify_document(self, text: str) -> Dict[str, Any]:
        """Classify document type."""
        # TODO: Implement actual API call
        return {"type": "unknown", "confidence": 0.0}

    async def parse_receipt(self, text: str) -> Dict[str, Any]:
        """Parse receipt text."""
        # TODO: Implement actual API call
        return {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "merchant": "Unknown",
            "amount": 0.0,
            "description": "Remote parsing not implemented",
            "source": "remote"
        }

    async def parse_bank_statement(self, text: str) -> List[Dict[str, Any]]:
        """Parse bank statement text."""
        # TODO: Implement actual API call
        return []


class NoOpAiService(AiServiceBase):
    """No-op AI service that doesn't enrich transactions."""

    async def categorise_transactions(
        self,
        transactions: List[Dict],
        categories: Dict[str, Any]
    ) -> List[Dict]:
        """Returns transactions unchanged."""
        return transactions

    async def enrich_merchant(
        self,
        merchant_name: str,
        description: str
    ) -> Dict[str, Any]:
        """Returns empty enrichment."""
        return {
            "aliases": [],
            "suggested_category": None
        }

    async def classify_document(self, text: str) -> Dict[str, Any]:
        """Returns unknown type."""
        return {"type": "unknown", "confidence": 0.0}

    async def parse_receipt(self, text: str) -> Dict[str, Any]:
        """Returns minimal parse."""
        return {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "merchant": "Unknown",
            "amount": 0.0,
            "description": "Unparsed receipt",
            "source": "noop"
        }

    async def parse_bank_statement(self, text: str) -> List[Dict[str, Any]]:
        """Returns empty list."""
        return []


def get_ai_service(
    provider: str = "noop",
    api_key: Optional[str] = None,
    local_server_url: Optional[str] = None,
    model: str = "mistral",
    vision_model: str = "llava"
) -> AiServiceBase:
    """
    Factory function to get the appropriate AI service.
    
    provider: 'noop', 'local', 'openai', 'anthropic', 'gemini'
    local_server_url: Ollama URL (default: http://localhost:11434)
    model: Model name for local service (default: mistral)
    vision_model: Vision model for image analysis (default: llava)
    """
    if provider == "noop":
        return NoOpAiService()
    elif provider == "local":
        return LocalAiService(
            server_url=local_server_url or "http://localhost:11434",
            model=model,
            vision_model=vision_model
        )
    elif provider in ["openai", "anthropic", "gemini"]:
        return RemoteAiService(provider=provider, api_key=api_key)
    else:
        raise ValueError(f"Unknown AI provider: {provider}")
