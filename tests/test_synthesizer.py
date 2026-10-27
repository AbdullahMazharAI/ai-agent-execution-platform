"""
tests/test_synthesizer.py
=========================
Unit tests for the Synthesizer (app/agent/synthesizer.py):
  - Uses MockLLMProvider to test LLM synthesis.
  - Verifies the prompt includes the goal and step results labelled by step number.
  - Verifies zero-step tasks instruct the model to answer from own knowledge.
  - Verifies temperature=0.3 and max_tokens=1500.
"""

from __future__ import annotations

import pytest

from app.agent.synthesizer import synthesize
from app.llm.gateway import LLMGateway
from app.llm.mock_provider import MockLLMProvider


@pytest.mark.asyncio
async def test_synthesize_with_step_results() -> None:
    expected_text = "Python is the primary language for AI, whereas JavaScript is gaining browser adoption."
    mock_provider = MockLLMProvider(responses=[expected_text])
    gateway = LLMGateway(primary=mock_provider, fallback=MockLLMProvider())

    goal = "Compare Python vs JavaScript for AI"
    step_results = [
        "Step 1: Python has PyTorch and TensorFlow ecosystems.",
        "Step 2: JavaScript supports TensorFlow.js and ONNX runtime web.",
    ]

    response = await synthesize(goal=goal, step_results=step_results, gateway=gateway)

    assert response.text == expected_text
    assert mock_provider.call_count == 1

    last_call = mock_provider.call_history[0]
    assert last_call["temperature"] == 0.3
    assert last_call["max_tokens"] == 1500

    user_message = next(
        msg["content"] for msg in last_call["messages"] if msg["role"] == "user"
    )
    assert goal in user_message
    assert "Step 1: Python has PyTorch" in user_message
    assert "Step 2: JavaScript supports" in user_message


@pytest.mark.asyncio
async def test_synthesize_without_step_results() -> None:
    expected_text = "Direct knowledge answer without any external tools."
    mock_provider = MockLLMProvider(responses=[expected_text])
    gateway = LLMGateway(primary=mock_provider, fallback=MockLLMProvider())

    goal = "Explain recursion simply"
    step_results: list[str] = []

    response = await synthesize(goal=goal, step_results=step_results, gateway=gateway)

    assert response.text == expected_text
    assert mock_provider.call_count == 1

    last_call = mock_provider.call_history[0]
    assert last_call["temperature"] == 0.3
    assert last_call["max_tokens"] == 1500

    user_message = next(
        msg["content"] for msg in last_call["messages"] if msg["role"] == "user"
    )
    assert goal in user_message
    assert "no step results" in user_message.lower()
    assert "own knowledge" in user_message.lower()
