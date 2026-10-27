"""
app/tools/base.py
=================
Abstract base class for all tools in the platform.

Every tool must implement:
  - name, description, input_schema (properties)
  - execute(args) → str
  - validate_input(args) → None (raises InvalidInputError)
"""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import Any

from app.core.errors import InvalidInputError, ToolTimeoutError, ToolUnavailableError

logger = logging.getLogger(__name__)


class Tool(ABC):
    """Abstract base class for platform tools.

    Subclasses must define:
      - name:         unique tool identifier
      - description:  human-readable purpose
      - input_schema: JSON Schema dict for valid arguments
      - execute:      async method that performs the work
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool name (e.g. 'web_search')."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """One-line description of what the tool does."""
        ...

    @property
    @abstractmethod
    def input_schema(self) -> dict[str, Any]:
        """JSON Schema describing accepted arguments."""
        ...

    def __init__(self, timeout_seconds: float = 30.0) -> None:
        self.timeout_seconds = timeout_seconds

    def validate_input(self, args: dict[str, Any]) -> None:
        """Validate tool arguments against ``input_schema``.

        Default implementation checks required fields and types.
        Override for tool-specific validation.

        Raises:
            InvalidInputError: when args are invalid.
        """
        schema = self.input_schema
        required = schema.get("required", [])
        properties = schema.get("properties", {})

        for field_name in required:
            if field_name not in args:
                raise InvalidInputError(
                    detail=f"Missing required field '{field_name}' for tool '{self.name}'.",
                    field=field_name,
                )

        for field_name, value in args.items():
            if field_name in properties:
                expected_type = properties[field_name].get("type")
                if expected_type and not self._check_type(value, expected_type):
                    raise InvalidInputError(
                        detail=(
                            f"Field '{field_name}' expects type '{expected_type}', "
                            f"got '{type(value).__name__}' for tool '{self.name}'."
                        ),
                        field=field_name,
                    )

    @abstractmethod
    async def execute(self, args: dict[str, Any]) -> str:
        """Run the tool with validated arguments and return a result string.

        Implementations should NOT handle their own timeout; the runner wraps
        this call in ``asyncio.wait_for``.

        Raises:
            ToolUnavailableError: external service unreachable.
        """
        ...

    async def run(self, args: dict[str, Any], timeout_override: float | None = None) -> str:
        """Validate, execute with timeout, and return the result.

        This is the main entry point called by the executor.

        Args:
            args: Tool arguments dict.
            timeout_override: Override the default timeout for this call.

        Returns:
            Tool output as a string.

        Raises:
            InvalidInputError: arguments fail validation.
            ToolTimeoutError: execution exceeds timeout.
            ToolUnavailableError: external dependency unavailable.
        """
        self.validate_input(args)
        timeout = timeout_override or self.timeout_seconds
        start = time.monotonic()

        try:
            result = await asyncio.wait_for(self.execute(args), timeout=timeout)
        except asyncio.TimeoutError:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.warning(
                "Tool '%s' timed out after %dms (limit=%ds)",
                self.name, elapsed_ms, timeout,
            )
            raise ToolTimeoutError(tool_name=self.name, timeout_ms=elapsed_ms)

        elapsed_ms = int((time.monotonic() - start) * 1000)
        logger.info("Tool '%s' completed in %dms", self.name, elapsed_ms)
        return result

    @staticmethod
    def _check_type(value: Any, json_type: str) -> bool:
        """Check whether ``value`` conforms to a JSON Schema type string."""
        type_map = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        expected = type_map.get(json_type)
        if expected is None:
            return True  # unknown type — skip check
        return isinstance(value, expected)
