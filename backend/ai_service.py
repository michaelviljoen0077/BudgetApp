"""
AI service for transaction categorization (via a local Ollama server).

Configured with environment variables:
    BUDGETAPP_AI_PROVIDER  "local" (Ollama, default) or "noop" (AI disabled)
    OLLAMA_URL             default http://localhost:11434
    OLLAMA_MODEL           default mistral
    OLLAMA_TIMEOUT         seconds per request, default 120
"""
import json
import logging
import os
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class AiUnavailableError(Exception):
    """Raised when the AI backend is disabled or cannot be reached."""


class AiServiceBase(ABC):
    """Abstract base for AI service implementations."""

    @abstractmethod
    async def complete(self, prompt: str) -> str:
        """Send a prompt and return the raw text response."""

    async def categorise_transactions(
        self, transactions: List[Dict], category_paths: List[str]
    ) -> Dict[str, str]:
        """
        Suggest categories for uncategorized transactions.
        Returns a mapping of transaction id -> suggested category path. Only
        suggestions that match an existing category are returned.
        """
        if not category_paths:
            return {}

        valid = set(category_paths)
        categories_str = "\n".join(f"- {path}" for path in sorted(category_paths))
        suggestions = {}

        for trans in transactions:
            if trans.get("category_path"):
                continue

            prompt = f"""You are a South African financial categorization expert. Given a transaction, respond with the MOST SPECIFIC matching category from the hierarchy.

IMPORTANT RULES:
1. Use the full path format "Parent/Child" for subcategories (e.g., "Medical/Prescriptions", "Transport/Petrol")
2. Only use the parent category if no specific subcategory matches
3. Match common South African merchants and terminology

Available categories (use exact format):
{categories_str}

Transaction:
- Description: {trans.get("description", "")}
- Merchant: {trans.get("merchant", "")}
- Amount: R{trans.get("amount", 0)}

Respond with ONLY the category path, nothing else."""

            try:
                category_path = (await self.complete(prompt)).strip().strip('"')
            except AiUnavailableError:
                raise
            except Exception as e:
                logger.warning("AI categorization failed for %r: %s", trans.get("description"), e)
                continue

            if category_path in valid:
                suggestions[trans["id"]] = category_path

        return suggestions


class LocalAiService(AiServiceBase):
    """Local LLM service via Ollama's HTTP API."""

    def __init__(self, server_url: str, model: str, timeout: float):
        self.server_url = server_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    async def complete(self, prompt: str) -> str:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.server_url}/api/generate",
                    json={"model": self.model, "prompt": prompt, "stream": False},
                )
        except httpx.TransportError as e:
            raise AiUnavailableError(f"Cannot reach Ollama at {self.server_url}: {e}") from e

        if response.status_code == 404:
            raise AiUnavailableError(f"Model '{self.model}' not found. Run: ollama pull {self.model}")
        response.raise_for_status()
        return response.json().get("response", "").strip()


class NoOpAiService(AiServiceBase):
    """AI disabled: every call reports that AI is unavailable."""

    async def complete(self, prompt: str) -> str:
        raise AiUnavailableError("AI is disabled (BUDGETAPP_AI_PROVIDER=noop)")


def extract_json(text: str) -> Optional[Any]:
    """Pull the first JSON object out of an LLM response, or None."""
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return None
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return None


def get_ai_service(provider: Optional[str] = None) -> AiServiceBase:
    """Build the AI service selected by BUDGETAPP_AI_PROVIDER (or `provider`)."""
    provider = provider or os.environ.get("BUDGETAPP_AI_PROVIDER", "local")
    if provider == "noop":
        return NoOpAiService()
    if provider == "local":
        return LocalAiService(
            server_url=os.environ.get("OLLAMA_URL", "http://localhost:11434"),
            model=os.environ.get("OLLAMA_MODEL", "mistral"),
            timeout=float(os.environ.get("OLLAMA_TIMEOUT", "120")),
        )
    raise ValueError(f"Unknown AI provider: {provider!r} (expected 'local' or 'noop')")
