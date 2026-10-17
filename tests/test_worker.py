"""
tests/test_worker.py
====================
Unit tests for the background worker skeleton in app/workers/execute_task.py.
"""

from __future__ import annotations

import pytest

from app.workers.execute_task import execute_task


@pytest.mark.asyncio
async def test_execute_task_skeleton() -> None:
    """Verifies that the Week 1 stub executes cleanly and returns expected structure."""
    ctx = {}
    task_id = "test-task-123"
    result = await execute_task(ctx, task_id)

    assert result["status"] == "stub_complete"
    assert result["task_id"] == task_id
    assert "elapsed_ms" in result
