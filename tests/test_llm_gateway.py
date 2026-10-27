"""
tests/test_llm_gateway.py
=========================
Unit tests for the LLM Gateway and providers:
  - LLMGateway fallback mechanism with MockLLMProvider (429, 500, timeout)
  - GroqProvider with httpx MockTransport
  - GeminiProvider with httpx MockTransport
  - was_fallback flag verification (True only when Gemini answers)
  - No real API calls are made.
"""

from __future__ import annotations

import httpx
import pytest

from app.core.errors import LLMError, LLMRateLimitError, LLMTimeoutError
from app.llm.gateway import LLMGateway
from app.llm.gemini_provider import GeminiProvider
from app.llm.groq_provider import GroqProvider
from app.llm.mock_provider import MockLLMProvider
from app.llm.models import LLMResponse


# ══════════════════════════════════════════════════════════════════════════════
# LLMGateway Tests with MockLLMProvider
# ══════════════════════════════════════════════════════════════════════════════
class TestLLMGatewayFallback:
    @pytest.mark.asyncio
    async def test_primary_succeeds_no_fallback(self) -> None:
        primary = MockLLMProvider(responses=["Primary response"], provider="groq")
        fallback = MockLLMProvider(responses=["Fallback response"], provider="gemini")
        gateway = LLMGateway(primary=primary, fallback=fallback)

        response = await gateway.complete(messages=[{"role": "user", "content": "hi"}])
        assert response.text == "Primary response"
        assert response.was_fallback is False
        assert primary.call_count == 1
        assert fallback.call_count == 0

    @pytest.mark.asyncio
    async def test_fallback_on_429_rate_limit(self) -> None:
        primary = MockLLMProvider(error=LLMRateLimitError(provider="groq"), provider="groq")
        fallback = MockLLMProvider(responses=["Gemini fallback on 429"], provider="gemini")
        gateway = LLMGateway(primary=primary, fallback=fallback)

        response = await gateway.complete(messages=[{"role": "user", "content": "hi"}])
        assert response.text == "Gemini fallback on 429"
        assert response.was_fallback is True
        assert response.provider == "gemini"
        assert primary.call_count == 1
        assert fallback.call_count == 1

    @pytest.mark.asyncio
    async def test_fallback_on_500_server_error(self) -> None:
        primary = MockLLMProvider(
            error=LLMError(detail="Groq server error: 500", provider="groq"),
            provider="groq",
        )
        fallback = MockLLMProvider(responses=["Gemini fallback on 500"], provider="gemini")
        gateway = LLMGateway(primary=primary, fallback=fallback)

        response = await gateway.complete(messages=[{"role": "user", "content": "hi"}])
        assert response.text == "Gemini fallback on 500"
        assert response.was_fallback is True
        assert primary.call_count == 1
        assert fallback.call_count == 1

    @pytest.mark.asyncio
    async def test_fallback_on_timeout(self) -> None:
        primary = MockLLMProvider(
            error=LLMTimeoutError(provider="groq", timeout_ms=5000),
            provider="groq",
        )
        fallback = MockLLMProvider(responses=["Gemini fallback on timeout"], provider="gemini")
        gateway = LLMGateway(primary=primary, fallback=fallback)

        response = await gateway.complete(messages=[{"role": "user", "content": "hi"}])
        assert response.text == "Gemini fallback on timeout"
        assert response.was_fallback is True
        assert primary.call_count == 1
        assert fallback.call_count == 1

    @pytest.mark.asyncio
    async def test_both_providers_fail_raises_llm_error(self) -> None:
        primary = MockLLMProvider(
            error=LLMRateLimitError(provider="groq"),
            provider="groq",
        )
        fallback = MockLLMProvider(
            error=LLMError(detail="Gemini error: 503", provider="gemini"),
            provider="gemini",
        )
        gateway = LLMGateway(primary=primary, fallback=fallback)

        with pytest.raises(LLMError) as exc_info:
            await gateway.complete(messages=[{"role": "user", "content": "hi"}])
        assert "All LLM providers failed" in str(exc_info.value.detail)


# ══════════════════════════════════════════════════════════════════════════════
# Provider HTTP Tests with MockTransport
# ══════════════════════════════════════════════════════════════════════════════
class TestProvidersWithMockTransport:
    @pytest.mark.asyncio
    async def test_groq_provider_success(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            content = {
                "choices": [{"message": {"content": "Groq answer"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 8},
                "model": "llama-3.1-8b-instant",
            }
            return httpx.Response(200, json=content)

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        provider = GroqProvider(client=client)

        resp = await provider.complete([{"role": "user", "content": "hello"}])
        assert resp.text == "Groq answer"
        assert resp.prompt_tokens == 12
        assert resp.completion_tokens == 8
        assert resp.provider == "groq"

    @pytest.mark.asyncio
    async def test_groq_provider_429(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, json={"error": "rate limit"})

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        provider = GroqProvider(client=client)

        with pytest.raises(LLMRateLimitError):
            await provider.complete([{"role": "user", "content": "hello"}])

    @pytest.mark.asyncio
    async def test_gemini_provider_success(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            content = {
                "candidates": [
                    {
                        "content": {"parts": [{"text": "Gemini answer"}]},
                        "finishReason": "STOP",
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 15,
                    "candidatesTokenCount": 9,
                },
            }
            return httpx.Response(200, json=content)

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        provider = GeminiProvider(client=client)

        resp = await provider.complete([{"role": "user", "content": "hello"}])
        assert resp.text == "Gemini answer"
        assert resp.prompt_tokens == 15
        assert resp.completion_tokens == 9
        assert resp.provider == "gemini"

    @pytest.mark.asyncio
    async def test_gemini_provider_500(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={"error": "internal"})

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        provider = GeminiProvider(client=client)

        with pytest.raises(LLMError):
            await provider.complete([{"role": "user", "content": "hello"}])

    @pytest.mark.asyncio
    async def test_gateway_with_mock_transports_fallback(self) -> None:
        def groq_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, json={"error": "rate_limit"})

        def gemini_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "candidates": [
                        {"content": {"parts": [{"text": "Answer from Gemini fallback"}]}}
                    ],
                    "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5},
                },
            )

        groq_client = httpx.AsyncClient(transport=httpx.MockTransport(groq_handler))
        gemini_client = httpx.AsyncClient(transport=httpx.MockTransport(gemini_handler))

        primary = GroqProvider(client=groq_client)
        fallback = GeminiProvider(client=gemini_client)
        gateway = LLMGateway(primary=primary, fallback=fallback)

        response = await gateway.complete([{"role": "user", "content": "test"}])
        assert response.text == "Answer from Gemini fallback"
        assert response.was_fallback is True
        assert response.provider == "gemini"
