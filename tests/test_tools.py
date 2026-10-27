"""
tests/test_tools.py
===================
Unit tests for the Tool System:
  - Base Tool input validation (missing fields, wrong types)
  - MockTool execution
  - ToolRegistry (register, get, duplicate-name rejection, list, validate_args)
  - FileTool (read file, path traversal rejection, missing file)
  - PythonTool (code execution, timeout with while True)
  - DuckDuckGoSearchTool (mocked _search)
"""

from __future__ import annotations

import os
import tempfile
from unittest.mock import AsyncMock, patch

import pytest

from app.core.errors import InvalidInputError, ToolTimeoutError, ToolUnavailableError
from app.tools.base import Tool
from app.tools.file_tool import FileTool
from app.tools.mock_tool import MockTool
from app.tools.python_tool import PythonTool
from app.tools.registry import ToolRegistry
from app.tools.web_search import DuckDuckGoSearchTool


# ══════════════════════════════════════════════════════════════════════════════
# Base Tool & MockTool Tests
# ══════════════════════════════════════════════════════════════════════════════
class TestBaseAndMockTool:
    @pytest.mark.asyncio
    async def test_mock_tool_execution(self) -> None:
        tool = MockTool(response="custom output")
        result = await tool.run({"input": "hello"})
        assert result == "custom output"

    def test_validate_input_missing_required_field(self) -> None:
        tool = MockTool()
        with pytest.raises(InvalidInputError) as exc_info:
            tool.validate_input({})
        assert "Missing required field 'input'" in str(exc_info.value.detail)
        assert exc_info.value.context.get("field") == "input"

    def test_validate_input_wrong_type(self) -> None:
        tool = MockTool()
        with pytest.raises(InvalidInputError) as exc_info:
            tool.validate_input({"input": 12345})
        assert "expects type 'string'" in str(exc_info.value.detail)

    def test_validate_input_valid(self) -> None:
        tool = MockTool()
        # Should not raise
        tool.validate_input({"input": "valid string"})


# ══════════════════════════════════════════════════════════════════════════════
# Tool Registry Tests
# ══════════════════════════════════════════════════════════════════════════════
class TestToolRegistry:
    def test_register_and_get(self) -> None:
        registry = ToolRegistry()
        tool = MockTool()
        registry.register(tool)

        assert registry.has("mock_tool")
        assert registry.get("mock_tool") is tool
        assert "mock_tool" in registry.tool_names

    def test_register_duplicate_name_raises(self) -> None:
        registry = ToolRegistry()
        tool1 = MockTool()
        tool2 = MockTool()
        registry.register(tool1)

        with pytest.raises(ValueError) as exc_info:
            registry.register(tool2)
        assert "already registered" in str(exc_info.value)

    def test_get_unregistered_tool_raises(self) -> None:
        registry = ToolRegistry()
        with pytest.raises(KeyError):
            registry.get("nonexistent_tool")

    def test_list_tools(self) -> None:
        registry = ToolRegistry()
        registry.register(MockTool())
        tools = registry.list_tools()
        assert len(tools) == 1
        assert tools[0]["name"] == "mock_tool"
        assert "description" in tools[0]
        assert "input_schema" in tools[0]

    def test_validate_args(self) -> None:
        registry = ToolRegistry()
        registry.register(MockTool())

        # Valid args pass
        registry.validate_args("mock_tool", {"input": "test"})

        # Invalid args raise InvalidInputError
        with pytest.raises(InvalidInputError):
            registry.validate_args("mock_tool", {})


# ══════════════════════════════════════════════════════════════════════════════
# FileTool Tests
# ══════════════════════════════════════════════════════════════════════════════
class TestFileTool:
    @pytest.mark.asyncio
    async def test_file_tool_read_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "test.txt")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("Platform file content")

            tool = FileTool(root_dir=tmpdir)
            tool.validate_input({"path": "test.txt"})
            content = await tool.execute({"path": "test.txt"})
            assert content == "Platform file content"

    def test_file_tool_path_traversal_rejection(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = FileTool(root_dir=tmpdir)
            with pytest.raises(InvalidInputError) as exc_info:
                tool.validate_input({"path": "../../etc/passwd"})
            assert "Path traversal detected" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_file_tool_missing_file_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = FileTool(root_dir=tmpdir)
            with pytest.raises(ToolUnavailableError):
                await tool.execute({"path": "does_not_exist.txt"})


# ══════════════════════════════════════════════════════════════════════════════
# PythonTool Tests
# ══════════════════════════════════════════════════════════════════════════════
class TestPythonTool:
    @pytest.mark.asyncio
    async def test_python_tool_exec_success(self) -> None:
        tool = PythonTool(timeout_seconds=5.0)
        tool.validate_input({"code": "print(2 + 2)"})
        result = await tool.execute({"code": "print(2 + 2)"})
        assert "4" in result

    @pytest.mark.asyncio
    async def test_python_tool_timeout(self) -> None:
        # Override with 1s timeout and infinite loop
        tool = PythonTool(timeout_seconds=1.0)
        with pytest.raises(ToolTimeoutError):
            await tool.execute({"code": "while True: pass"})


# ══════════════════════════════════════════════════════════════════════════════
# DuckDuckGoSearchTool Tests (Mocked)
# ══════════════════════════════════════════════════════════════════════════════
class TestDuckDuckGoSearchTool:
    @pytest.mark.asyncio
    async def test_search_success_mocked(self) -> None:
        tool = DuckDuckGoSearchTool()
        mock_results = [
            {"title": "FastAPI", "href": "https://fastapi.tiangolo.com", "body": "FastAPI framework"},
            {"title": "Python", "href": "https://python.org", "body": "Python language"},
        ]

        with patch.object(tool, "_search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = mock_results
            result = await tool.execute({"query": "FastAPI python"})
            assert "1. FastAPI" in result
            assert "https://fastapi.tiangolo.com" in result
            assert "2. Python" in result

    @pytest.mark.asyncio
    async def test_search_empty_results(self) -> None:
        tool = DuckDuckGoSearchTool()
        with patch.object(tool, "_search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = []
            result = await tool.execute({"query": "nonexistent query xyz123"})
            assert result == "No results found."

    @pytest.mark.asyncio
    async def test_search_failure_maps_to_tool_unavailable(self) -> None:
        tool = DuckDuckGoSearchTool()
        with patch.object(tool, "_search", side_effect=RuntimeError("Network down")):
            with pytest.raises(ToolUnavailableError):
                await tool.execute({"query": "python"})
