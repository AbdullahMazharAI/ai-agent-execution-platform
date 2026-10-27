"""
tests/test_planner.py
=====================
Unit tests for the Planner (app/agent/planner.py):
  - Valid JSON plan generation
  - Fenced JSON plan (```json ... ``` and ``` ... ```)
  - Invalid JSON raises PlannerError
  - Unknown tool name raises PlannerError
  - Plan with >10 steps raises PlannerError
  - Empty steps raises PlannerError
"""

from __future__ import annotations

import json
import pytest

from app.agent.planner import Planner
from app.core.errors import PlannerError
from app.llm.gateway import LLMGateway
from app.llm.mock_provider import MockLLMProvider
from app.tools.mock_tool import MockTool
from app.tools.registry import ToolRegistry


def _create_planner(canned_response: str) -> Planner:
    primary = MockLLMProvider(responses=[canned_response], provider="mock")
    fallback = MockLLMProvider(responses=[], provider="mock_fallback")
    gateway = LLMGateway(primary=primary, fallback=fallback)

    registry = ToolRegistry()
    registry.register(MockTool())
    return Planner(gateway=gateway, registry=registry)


class TestPlanner:
    @pytest.mark.asyncio
    async def test_valid_json_plan(self) -> None:
        plan_json = json.dumps({
            "steps": [
                {
                    "step_number": 1,
                    "description": "Run mock tool",
                    "tool_name": "mock_tool",
                    "tool_args": {"input": "test input"},
                }
            ]
        })
        planner = _create_planner(plan_json)
        plan, response = await planner.generate_plan("Do something")

        assert len(plan.steps) == 1
        assert plan.steps[0].step_number == 1
        assert plan.steps[0].tool_name == "mock_tool"
        assert plan.steps[0].tool_args == {"input": "test input"}
        assert response.text == plan_json

    @pytest.mark.asyncio
    async def test_fenced_json_plan(self) -> None:
        raw_json = json.dumps({
            "steps": [
                {
                    "step_number": 1,
                    "description": "Fenced step",
                    "tool_name": "mock_tool",
                    "tool_args": {"input": "fenced"},
                }
            ]
        })
        fenced = f"```json\n{raw_json}\n```"
        planner = _create_planner(fenced)
        plan, _ = await planner.generate_plan("Do fenced task")

        assert len(plan.steps) == 1
        assert plan.steps[0].description == "Fenced step"

    @pytest.mark.asyncio
    async def test_generic_fenced_json_plan(self) -> None:
        raw_json = json.dumps({
            "steps": [
                {
                    "step_number": 1,
                    "description": "Generic fenced",
                    "tool_name": "mock_tool",
                    "tool_args": {"input": "generic"},
                }
            ]
        })
        fenced = f"```\n{raw_json}\n```"
        planner = _create_planner(fenced)
        plan, _ = await planner.generate_plan("Do task")

        assert len(plan.steps) == 1
        assert plan.steps[0].description == "Generic fenced"

    @pytest.mark.asyncio
    async def test_invalid_json_raises_planner_error(self) -> None:
        planner = _create_planner("This is not valid JSON at all")
        with pytest.raises(PlannerError) as exc_info:
            await planner.generate_plan("Do invalid task")
        assert "invalid JSON" in str(exc_info.value.detail)
        assert exc_info.value.context.get("reason") == "invalid_json"

    @pytest.mark.asyncio
    async def test_unknown_tool_name_raises_planner_error(self) -> None:
        plan_json = json.dumps({
            "steps": [
                {
                    "step_number": 1,
                    "description": "Use missing tool",
                    "tool_name": "nonexistent_tool_xyz",
                    "tool_args": {},
                }
            ]
        })
        planner = _create_planner(plan_json)
        with pytest.raises(PlannerError) as exc_info:
            await planner.generate_plan("Do unknown tool task")
        assert "references unknown tool 'nonexistent_tool_xyz'" in str(exc_info.value.detail)
        assert exc_info.value.context.get("reason") == "unknown_tool"

    @pytest.mark.asyncio
    async def test_more_than_10_steps_raises_planner_error(self) -> None:
        steps = [
            {
                "step_number": i,
                "description": f"Step {i}",
                "tool_name": "mock_tool",
                "tool_args": {"input": f"arg {i}"},
            }
            for i in range(1, 12)  # 11 steps
        ]
        plan_json = json.dumps({"steps": steps})
        planner = _create_planner(plan_json)
        with pytest.raises(PlannerError) as exc_info:
            await planner.generate_plan("Do 11 steps task")
        assert "validation failed" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_empty_steps_raises_planner_error(self) -> None:
        plan_json = json.dumps({})
        planner = _create_planner(plan_json)
        with pytest.raises(PlannerError) as exc_info:
            await planner.generate_plan("Do empty task")
        assert "validation failed" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_empty_steps_plan_accepted(self) -> None:
        plan_json = json.dumps({"steps": []})
        planner = _create_planner(plan_json)
        plan, response = await planner.generate_plan("Do empty steps task")
        assert len(plan.steps) == 0
        assert plan.steps == []
        assert response.text == plan_json
