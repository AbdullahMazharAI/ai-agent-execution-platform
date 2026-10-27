"""
app/llm/base.py
===============
Abstract base class for LLM providers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.llm.models import LLMResponse


class LLMProvider(ABC):
    """Abstract interface for an LLM provider (Groq, Gemini, etc.)."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider identifier."""
        ...

    @abstractmethod
    async def complete(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """Send a chat completion request.

        Args:
            messages:    List of {"role": "...", "content": "..."} dicts.
            temperature: Sampling temperature.
            max_tokens:  Maximum tokens in the completion.

        Returns:
            An LLMResponse with the generated text and token counts.
        """
        ...
