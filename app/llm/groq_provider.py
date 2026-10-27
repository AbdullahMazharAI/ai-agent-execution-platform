"""
app/llm/groq_provider.py
=========================
LLM provider for Groq's OpenAI-compatible API.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import get_settings
from app.core.errors import LLMError, LLMRateLimitError, LLMTimeoutError
from app.llm.base import LLMProvider
from app.llm.models import LLMResponse

logger = logging.getLogger(__name__)

_GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


class GroqProvider(LLMProvider):
    """Groq LLM provider using their OpenAI-compatible endpoint.

    Requires ``GROQ_API_KEY`` and optionally ``GROQ_MODEL`` in config.
    """

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        settings = get_settings()
        self._api_key = settings.GROQ_API_KEY or ""
        self._model = settings.GROQ_MODEL
        self._timeout = settings.LLM_TIMEOUT_SECONDS
        self._client = client

    @property
    def provider_name(self) -> str:
        return "groq"

    async def complete(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """Call Groq's chat completions endpoint.

        Raises:
            LLMRateLimitError: on 429 responses.
            LLMTimeoutError: on request timeout.
            LLMError: on other HTTP errors.
        """
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        client = self._client or httpx.AsyncClient(timeout=self._timeout)
        should_close = self._client is None

        try:
            response = await client.post(
                _GROQ_API_URL,
                json=payload,
                headers=headers,
            )

            if response.status_code == 429:
                raise LLMRateLimitError(provider=self.provider_name)

            if response.status_code >= 500:
                raise LLMError(
                    detail=f"Groq server error: {response.status_code}",
                    provider=self.provider_name,
                )

            response.raise_for_status()
            data = response.json()

            choice = data["choices"][0]
            usage = data.get("usage", {})

            return LLMResponse(
                text=choice["message"]["content"],
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                finish_reason=choice.get("finish_reason", "stop"),
                provider=self.provider_name,
                model=data.get("model", self._model),
            )

        except (httpx.TimeoutException, httpx.ConnectTimeout):
            raise LLMTimeoutError(
                provider=self.provider_name,
                timeout_ms=int(self._timeout * 1000),
            )
        except (LLMRateLimitError, LLMTimeoutError, LLMError):
            raise
        except httpx.HTTPStatusError as exc:
            raise LLMError(
                detail=f"Groq HTTP error: {exc.response.status_code}",
                provider=self.provider_name,
            ) from exc
        except Exception as exc:
            raise LLMError(
                detail=f"Groq request failed: {exc}",
                provider=self.provider_name,
            ) from exc
        finally:
            if should_close:
                await client.aclose()
