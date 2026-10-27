"""
app/agent/synthesizer.py
========================
Synthesizes the final answer to the user's goal from the plan execution results
using the LLM Gateway.
"""

from __future__ import annotations

import logging

from app.llm.gateway import LLMGateway
from app.llm.models import LLMResponse

logger = logging.getLogger(__name__)


async def synthesize(
    goal: str,
    step_results: list[str],
    gateway: LLMGateway,
) -> LLMResponse:
    """Synthesize a final answer for the user's goal based on step execution results.

    Args:
        goal: The user's goal.
        step_results: List of step execution result strings (if any).
        gateway: LLMGateway instance to complete the prompt.

    Returns:
        LLMResponse containing synthesized text and token usage.
    """
    if step_results:
        formatted_steps = []
        for idx, res in enumerate(step_results, start=1):
            if res.startswith(f"Step {idx}:"):
                formatted_steps.append(res)
            else:
                formatted_steps.append(f"Step {idx}: {res}")
        steps_text = "\n".join(formatted_steps)
        prompt = (
            f"Goal:\n{goal}\n\n"
            f"Step Results:\n{steps_text}\n\n"
            f"Based on the step results above, synthesize a complete and accurate answer to accomplish the goal."
        )
    else:
        prompt = (
            f"Goal:\n{goal}\n\n"
            f"There are no step results. Please answer the goal directly from your own knowledge."
        )

    messages = [
        {
            "role": "system",
            "content": (
                "You are an AI synthesis assistant. Your task is to provide a comprehensive, "
                "clear, and well-structured answer to the user's goal using the provided step "
                "results or your own knowledge when no tools were needed."
            ),
        },
        {"role": "user", "content": prompt},
    ]

    response = await gateway.complete(
        messages=messages,
        temperature=0.3,
        max_tokens=1500,
    )
    return response
