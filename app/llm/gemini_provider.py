"""
app/llm/gemini_provider.py
===========================
LLM provider for Google Gemini REST API.
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

_GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiProvider(LLMProvider):
    """Google Gemini LLM provider via REST API.

    Requires ``GEMINI_API_KEY`` and optionally ``GEMINI_MODEL`` in config.
    """

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        settings = get_settings()
        self._api_key = settings.GEMINI_API_KEY or ""
        self._model = settings.GEMINI_MODEL
        self._timeout = settings.LLM_TIMEOUT_SECONDS
        self._client = client

    @property
    def provider_name(self) -> str:
        return "gemini"

    async def complete(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """Call Gemini's generateContent endpoint.

        Converts OpenAI-style messages to Gemini's format.

        Raises:
            LLMRateLimitError: on 429 responses.
            LLMTimeoutError: on request timeout.
            LLMError: on other HTTP errors.
        """
        # Convert messages to Gemini format
        contents = []
        system_text = ""
        for msg in messages:
            role = msg["role"]
            if role == "system":
                system_text = msg["content"]
            elif role == "user":
                contents.append({
                    "role": "user",
                    "parts": [{"text": msg["content"]}],
                })
            elif role == "assistant":
                contents.append({
                    "role": "model",
                    "parts": [{"text": msg["content"]}],
                })

        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        if system_text:
            payload["systemInstruction"] = {
                "parts": [{"text": system_text}]
            }

        url = f"{_GEMINI_API_BASE}/{self._model}:generateContent?key={self._api_key}"

        client = self._client or httpx.AsyncClient(timeout=self._timeout)
        should_close = self._client is None

        try:
            response = await client.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )

            if response.status_code == 429:
                raise LLMRateLimitError(provider=self.provider_name)

            if response.status_code >= 500:
                raise LLMError(
                    detail=f"Gemini server error: {response.status_code}",
                    provider=self.provider_name,
                )

            response.raise_for_status()
            data = response.json()

            # Extract text from response
            candidates = data.get("candidates", [])
            if not candidates:
                raise LLMError(
                    detail="Gemini returned no candidates.",
                    provider=self.provider_name,
                )

            text = ""
            parts = candidates[0].get("content", {}).get("parts", [])
            for part in parts:
                text += part.get("text", "")

            # Token usage
            usage = data.get("usageMetadata", {})
            finish_reason = candidates[0].get("finishReason", "STOP").lower()

            return LLMResponse(
                text=text,
                prompt_tokens=usage.get("promptTokenCount", 0),
                completion_tokens=usage.get("candidatesTokenCount", 0),
                finish_reason=finish_reason,
                provider=self.provider_name,
                model=self._model,
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
                detail=f"Gemini HTTP error: {exc.response.status_code}",
                provider=self.provider_name,
            ) from exc
        except Exception as exc:
            raise LLMError(
                detail=f"Gemini request failed: {exc}",
                provider=self.provider_name,
            ) from exc
        finally:
            if should_close:
                await client.aclose()
