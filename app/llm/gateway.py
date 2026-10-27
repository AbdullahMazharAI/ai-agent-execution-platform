"""
app/llm/gateway.py
==================
LLM Gateway — unified entry point for LLM calls with automatic fallback.

Strategy: Try Groq first. On 429 / 5xx / timeout, fall back to Gemini.
No retries within the gateway (retries are Week 4).
"""

from __future__ import annotations

import logging
import time
from typing import Any

from app.core.errors import LLMError, LLMRateLimitError, LLMTimeoutError
from app.llm.base import LLMProvider
from app.llm.models import LLMResponse

logger = logging.getLogger(__name__)


class LLMGateway:
    """Unified LLM gateway with primary + fallback provider.

    Args:
        primary:  The preferred LLM provider (e.g. Groq).
        fallback: The fallback LLM provider (e.g. Gemini).
    """

    def __init__(self, primary: LLMProvider, fallback: LLMProvider) -> None:
        self._primary = primary
        self._fallback = fallback

    async def complete(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """Send a completion request, falling back on transient errors.

        Fallback triggers on:
          - LLMRateLimitError (429)
          - LLMError with 5xx status
          - LLMTimeoutError

        Returns:
            LLMResponse with ``was_fallback=True`` if the fallback answered.

        Raises:
            LLMError: if both providers fail.
        """
        start = time.monotonic()

        # ── Try primary ───────────────────────────────────────────────────
        try:
            response = await self._primary.complete(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.info(
                "LLM primary (%s) responded in %dms",
                self._primary.provider_name,
                elapsed_ms,
            )
            response.was_fallback = False
            return response

        except (LLMRateLimitError, LLMTimeoutError) as exc:
            logger.warning(
                "LLM primary (%s) failed with %s, falling back to %s",
                self._primary.provider_name,
                type(exc).__name__,
                self._fallback.provider_name,
            )
        except LLMError as exc:
            logger.warning(
                "LLM primary (%s) failed: %s, falling back to %s",
                self._primary.provider_name,
                exc.detail,
                self._fallback.provider_name,
            )

        # ── Try fallback ──────────────────────────────────────────────────
        try:
            response = await self._fallback.complete(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.info(
                "LLM fallback (%s) responded in %dms",
                self._fallback.provider_name,
                elapsed_ms,
            )
            response.was_fallback = True
            return response

        except Exception as exc:
            logger.error(
                "LLM fallback (%s) also failed: %s",
                self._fallback.provider_name,
                exc,
            )
            raise LLMError(
                detail=f"All LLM providers failed. Last error: {exc}",
                provider=self._fallback.provider_name,
            ) from exc
