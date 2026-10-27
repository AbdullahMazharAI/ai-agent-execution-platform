"""
app/tools/mock_tool.py
======================
Deterministic mock tool for testing.
"""

from __future__ import annotations

from typing import Any

from app.tools.base import Tool


class MockTool(Tool):
    """A mock tool that returns deterministic output for tests.

    Args:
        response: The fixed string to return on every execution.
        timeout_seconds: Per-call timeout (default 30s).
    """

    def __init__(self, response: str = "mock result", timeout_seconds: float = 30.0) -> None:
        super().__init__(timeout_seconds=timeout_seconds)
        self._response = response

    @property
    def name(self) -> str:
        return "mock_tool"

    @property
    def description(self) -> str:
        return "A deterministic mock tool for testing."

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "input": {"type": "string", "description": "Any input text."},
            },
            "required": ["input"],
        }

    async def execute(self, args: dict[str, Any]) -> str:
        return self._response
