"""
app/agent/planner.py
====================
One-shot plan generation via LLM Gateway.

Sends the user's goal to the LLM with tool metadata and parses the
JSON plan. Validates via Pydantic and checks tool references against
the ToolRegistry.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.core.errors import PlannerError
from app.llm.gateway import LLMGateway
from app.llm.models import LLMResponse
from app.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

MAX_STEPS = 10


# ── Pydantic models for plan validation ──────────────────────────────────────

class PlanStep(BaseModel):
    """A single step in the execution plan."""
    step_number: int
    description: str
    tool_name: str
    tool_args: dict[str, Any] = Field(default_factory=dict)


class PlanModel(BaseModel):
    """Validated execution plan produced by the LLM."""
    steps: list[PlanStep]

    @field_validator("steps")
    @classmethod
    def check_max_steps(cls, v: list[PlanStep]) -> list[PlanStep]:
        if len(v) > MAX_STEPS:
            raise ValueError(f"Plan has {len(v)} steps, maximum is {MAX_STEPS}.")
        return v


# ── System prompt ────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a task planner for an AI agent platform. Given a user's goal and the \
available tools, produce an execution plan as a JSON object.

The plan MUST be valid JSON with this exact structure:
{{"steps": [{{"step_number": 1, "description": "...", "tool_name": "...", "tool_args": {{...}}}}]}}

Rules:
- Each step must use one of the available tools.
- Maximum {max_steps} steps.
- tool_args must match the tool's input_schema.
- Use web_search ONLY for current events, recent facts, or specific lookups.
- For explanations, comparisons, writing, or general knowledge, return {{"steps": []}} with no tool calls.
- Never use mock_tool for real work. mock_tool is for tests only.
- Do NOT include any text outside the JSON object.
"""


def _build_system_prompt(tools: list[dict[str, Any]]) -> str:
    """Build the system prompt with available tool descriptions."""
    tool_desc = "\n".join(
        f"- {t['name']}: {t['description']} (args: {json.dumps(t['input_schema'])})"
        for t in tools
    )
    return (
        _SYSTEM_PROMPT.format(max_steps=MAX_STEPS)
        + f"\nAvailable tools:\n{tool_desc}\n"
    )


def _strip_json_fences(text: str) -> str:
    """Remove ```json ... ``` fences and leading/trailing whitespace."""
    text = text.strip()
    # Remove ```json ... ``` or ``` ... ```
    pattern = r"^```(?:json)?\s*\n?(.*?)\n?\s*```$"
    match = re.match(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text


# ── Planner ──────────────────────────────────────────────────────────────────

class Planner:
    """Generates an execution plan from a user goal using the LLM Gateway.

    Args:
        gateway:  LLM Gateway instance.
        registry: ToolRegistry to validate tool references.
    """

    def __init__(self, gateway: LLMGateway, registry: ToolRegistry) -> None:
        self._gateway = gateway
        self._registry = registry

    async def generate_plan(self, goal: str) -> tuple[PlanModel, LLMResponse]:
        """Generate and validate a plan for the given goal.

        Args:
            goal: The user's high-level task description.

        Returns:
            Tuple of (validated PlanModel, LLMResponse with usage data).

        Raises:
            PlannerError: on invalid JSON, unknown tools, or too many steps.
        """
        tools = self._registry.list_tools()
        system_prompt = _build_system_prompt(tools)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": goal},
        ]

        llm_response = await self._gateway.complete(
            messages=messages,
            temperature=0.1,
            max_tokens=1000,
        )

        # Parse JSON from LLM response
        raw_text = _strip_json_fences(llm_response.text)

        try:
            plan_data = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise PlannerError(
                detail=f"LLM returned invalid JSON: {exc}",
                reason="invalid_json",
            ) from exc

        # Validate with Pydantic
        try:
            plan = PlanModel(**plan_data)
        except Exception as exc:
            raise PlannerError(
                detail=f"Plan validation failed: {exc}",
                reason="validation_failed",
            ) from exc

        # Verify all tool names exist in registry
        for step in plan.steps:
            if not self._registry.has(step.tool_name):
                raise PlannerError(
                    detail=(
                        f"Step {step.step_number} references unknown tool "
                        f"'{step.tool_name}'. Available tools: {self._registry.tool_names}"
                    ),
                    reason="unknown_tool",
                )

        logger.info("Plan generated: %d steps", len(plan.steps))
        return plan, llm_response
