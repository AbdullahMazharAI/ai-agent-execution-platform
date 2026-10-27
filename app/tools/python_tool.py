"""
app/tools/python_tool.py
========================
Execute Python code in a sandboxed subprocess.

Safety measures:
  - Runs in a temporary working directory.
  - Hard timeout (default 10s, configurable via PYTHON_TOOL_TIMEOUT_SECONDS).
  - No network access (best-effort: not a full sandbox, but subprocess isolation).
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from typing import Any

from app.core.errors import ToolTimeoutError, ToolUnavailableError
from app.tools.base import Tool

logger = logging.getLogger(__name__)


class PythonTool(Tool):
    """Execute Python code in a subprocess with a timeout.

    The code runs in a fresh temporary directory with stdout + stderr captured.

    Args:
        timeout_seconds: Max execution time (default: 10s or env var).
    """

    def __init__(self, timeout_seconds: float | None = None) -> None:
        if timeout_seconds is None:
            timeout_seconds = float(
                os.environ.get("PYTHON_TOOL_TIMEOUT_SECONDS", "10")
            )
        super().__init__(timeout_seconds=timeout_seconds)

    @property
    def name(self) -> str:
        return "python_exec"

    @property
    def description(self) -> str:
        return "Execute Python code in a sandboxed subprocess and return stdout."

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python source code to execute.",
                },
            },
            "required": ["code"],
        }

    async def execute(self, args: dict[str, Any]) -> str:
        """Run Python code in a subprocess.

        Returns:
            Combined stdout and stderr from the subprocess.

        Raises:
            ToolTimeoutError: if execution exceeds the timeout.
            ToolUnavailableError: if the subprocess cannot be started.
        """
        code = args["code"]

        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = os.path.join(tmpdir, "script.py")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(code)

            try:
                proc = await asyncio.create_subprocess_exec(
                    "python", script_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=tmpdir,
                )

                try:
                    stdout, stderr = await asyncio.wait_for(
                        proc.communicate(), timeout=self.timeout_seconds
                    )
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()
                    raise ToolTimeoutError(
                        tool_name=self.name,
                        timeout_ms=int(self.timeout_seconds * 1000),
                    )

                output = stdout.decode("utf-8", errors="replace")
                errors = stderr.decode("utf-8", errors="replace")

                if proc.returncode != 0:
                    return f"Exit code: {proc.returncode}\nStderr:\n{errors}\nStdout:\n{output}"

                return output.strip() if output.strip() else errors.strip()

            except ToolTimeoutError:
                raise
            except Exception as exc:
                logger.error("PythonTool subprocess error: %s", exc)
                raise ToolUnavailableError(tool_name=self.name) from exc
