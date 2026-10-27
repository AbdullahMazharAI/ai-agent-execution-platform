"""
app/llm/models.py
=================
Data classes for LLM responses.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LLMResponse:
    """Structured response from an LLM provider.

    Attributes:
        text:              Generated text content.
        prompt_tokens:     Number of tokens in the prompt.
        completion_tokens: Number of tokens in the completion.
        finish_reason:     Why generation stopped (e.g. 'stop', 'length').
        provider:          Which provider answered (e.g. 'groq', 'gemini').
        model:             Model name used.
        was_fallback:      True if this response came from the fallback provider.
    """

    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    finish_reason: str = "stop"
    provider: str = ""
    model: str = ""
    was_fallback: bool = False

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens
