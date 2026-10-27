"""
app/tools/file_tool.py
======================
Read-only file access tool, restricted to a configurable root directory.

Default root: ``./uploads`` (overridden via ``FILE_TOOL_ROOT`` env var).
All paths are resolved and checked against the root to prevent path traversal.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from app.core.errors import InvalidInputError, ToolUnavailableError
from app.tools.base import Tool

logger = logging.getLogger(__name__)


class FileTool(Tool):
    """Read files within a restricted directory tree.

    Args:
        root_dir: The root directory to restrict reads to.
        timeout_seconds: Per-call timeout.
    """

    def __init__(
        self,
        root_dir: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        super().__init__(timeout_seconds=timeout_seconds)
        if root_dir is None:
            root_dir = os.environ.get("FILE_TOOL_ROOT", "./uploads")
        self._root = Path(root_dir).resolve()

    @property
    def name(self) -> str:
        return "file_read"

    @property
    def description(self) -> str:
        return "Read the contents of a file within the allowed uploads directory."

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path to the file within the uploads directory.",
                },
            },
            "required": ["path"],
        }

    def validate_input(self, args: dict[str, Any]) -> None:
        """Check required fields and reject path traversal attempts."""
        super().validate_input(args)

        requested = (self._root / args["path"]).resolve()
        if not str(requested).startswith(str(self._root)):
            raise InvalidInputError(
                detail=f"Path traversal detected: '{args['path']}' escapes the allowed root.",
                field="path",
            )

    async def execute(self, args: dict[str, Any]) -> str:
        """Read and return the file contents as a string.

        Raises:
            ToolUnavailableError: if the file does not exist or cannot be read.
        """
        target = (self._root / args["path"]).resolve()

        if not target.exists():
            raise ToolUnavailableError(tool_name=self.name)

        try:
            return target.read_text(encoding="utf-8")
        except Exception as exc:
            logger.error("FileTool read error: %s", exc)
            raise ToolUnavailableError(tool_name=self.name) from exc
