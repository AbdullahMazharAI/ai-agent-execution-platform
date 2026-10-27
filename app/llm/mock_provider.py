"""
app/llm/mock_provider.py
=========================
Mock LLM provider for testing.
"""

from __future__ import annotations

from typing import Any

from app.core.errors import LLMError, LLMRateLimitError, LLMTimeoutError
from app.llm.base import LLMProvider
from app.llm.models import LLMResponse


class MockLLMProvider(LLMProvider):
    """Mock LLM provider that returns canned responses.

    Args:
        responses: List of LLMResponse objects or strings to return in order.
                   Strings are converted to LLMResponse with default values.
        error:     Optional exception to raise instead of returning a response.
        provider:  Provider name to use (default: "mock").
    """

    def __init__(
        self,
        responses: list[LLMResponse | str] | None = None,
        error: Exception | None = None,
        provider: str = "mock",
    ) -> None:
        self._responses: list[LLMResponse] = []
        self._error = error
        self._provider = provider
        self._call_count = 0
        self._call_history: list[dict[str, Any]] = []

        if responses:
            for r in responses:
                if isinstance(r, str):
                    self._responses.append(
                        LLMResponse(
                            text=r,
                            prompt_tokens=10,
                            completion_tokens=20,
                            provider=provider,
                        )
                    )
                else:
                    self._responses.append(r)

    @property
    def provider_name(self) -> str:
        return self._provider

    @property
    def call_count(self) -> int:
        return self._call_count

    @property
    def call_history(self) -> list[dict[str, Any]]:
        return self._call_history

    async def complete(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """Return canned response or raise configured error."""
        self._call_count += 1
        self._call_history.append({
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        })

        if self._error is not None:
            raise self._error

        if not self._responses:
            return LLMResponse(
                text="Mock response",
                prompt_tokens=10,
                completion_tokens=20,
                provider=self._provider,
            )

        # Cycle through responses
        idx = (self._call_count - 1) % len(self._responses)
        return self._responses[idx]
