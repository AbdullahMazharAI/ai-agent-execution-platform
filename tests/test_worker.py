"""
tests/test_worker.py
====================
Unit tests for the background worker in app/workers/execute_task.py.
  - Verifies Week 1 stub executes cleanly.
  - Verifies zero-step task lifecycle: PLANNING → SYNTHESIZING → COMPLETED.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.agent.planner import PlanModel
from app.db.models import Base, Task, TaskStatus, User
from app.llm.models import LLMResponse
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


@pytest.mark.asyncio
async def test_zero_step_task_lifecycle(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies that a task with zero plan steps progresses PLANNING → SYNTHESIZING → COMPLETED."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    user_id = uuid.uuid4()
    task_id = uuid.uuid4()

    async with session_factory() as session:
        user = User(id=user_id, username="worker_user", email="worker@example.com")
        session.add(user)
        task = Task(
            id=task_id,
            user_id=user_id,
            goal="Write a 3-sentence comparison of Python and JavaScript",
            status=TaskStatus.PENDING,
        )
        session.add(task)
        await session.commit()

    monkeypatch.setattr("app.database.async_session_factory", session_factory)

    # Track status transitions on the Task model
    status_history: list[TaskStatus] = []
    orig_setattr = Task.__setattr__

    def tracking_setattr(self: Task, name: str, value: Any) -> None:
        if name == "status":
            status_history.append(value)
        orig_setattr(self, name, value)

    monkeypatch.setattr(Task, "__setattr__", tracking_setattr)

    # Mock planner to return zero steps
    async def mock_generate_plan(self: Any, goal: str) -> tuple[PlanModel, LLMResponse]:
        plan = PlanModel(steps=[])
        llm_resp = LLMResponse(
            text='{"steps": []}',
            prompt_tokens=5,
            completion_tokens=5,
            provider="mock",
            model="mock",
        )
        return plan, llm_resp

    monkeypatch.setattr("app.agent.planner.Planner.generate_plan", mock_generate_plan)

    # Mock synthesizer
    async def mock_synthesize(goal: str, step_results: list[str], gateway: Any) -> LLMResponse:
        assert step_results == []
        return LLMResponse(
            text="Synthesized result for zero steps task.",
            prompt_tokens=12,
            completion_tokens=25,
            provider="mock",
            model="mock",
        )

    monkeypatch.setattr("app.workers.execute_task.synthesize", mock_synthesize)

    ctx: dict[str, Any] = {}
    result = await execute_task(ctx, str(task_id))

    assert result["status"] == "completed"
    assert status_history == [
        TaskStatus.PLANNING,
        TaskStatus.SYNTHESIZING,
        TaskStatus.COMPLETED,
    ]

    async with session_factory() as session:
        saved_task = (await session.execute(select(Task).where(Task.id == task_id))).scalar_one()
        assert saved_task.status == TaskStatus.COMPLETED
        assert saved_task.result == "Synthesized result for zero steps task."

    await engine.dispose()
