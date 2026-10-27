"""
app/tools/registry.py
=====================
Central tool registry — register, get, list, and validate tools.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.errors import InvalidInputError
from app.tools.base import Tool

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Registry of available tools.

    Usage::

        registry = ToolRegistry()
        registry.register(WebSearchTool())
        tool = registry.get("web_search")
        result = await tool.run({"query": "Python AI"})
    """

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool instance.

        Raises:
            ValueError: if a tool with the same name is already registered.
        """
        if tool.name in self._tools:
            raise ValueError(
                f"Tool '{tool.name}' is already registered. "
                f"Duplicate registration is not allowed."
            )
        self._tools[tool.name] = tool
        logger.info("Registered tool: %s", tool.name)

    def get(self, name: str) -> Tool:
        """Retrieve a tool by name.

        Raises:
            KeyError: if the tool is not registered.
        """
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' is not registered.")
        return self._tools[name]

    def list_tools(self) -> list[dict[str, Any]]:
        """Return metadata for all registered tools."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema,
            }
            for tool in self._tools.values()
        ]

    def has(self, name: str) -> bool:
        """Check whether a tool is registered."""
        return name in self._tools

    def validate_args(self, tool_name: str, args: dict[str, Any]) -> None:
        """Validate arguments for a named tool.

        Raises:
            KeyError: if the tool is not registered.
            InvalidInputError: if args are invalid.
        """
        tool = self.get(tool_name)
        tool.validate_input(args)

    @property
    def tool_names(self) -> list[str]:
        """Sorted list of registered tool names."""
        return sorted(self._tools.keys())
