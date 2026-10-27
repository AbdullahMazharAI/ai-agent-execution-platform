"""
tests/test_executor.py
======================
Integration tests for Executor (app/agent/executor.py):
  - Sequential execution of multiple MockTool steps
  - DB rows recorded for task_steps and tool_calls
  - Stops on tool failure (step marked FAILED, task marked FAILED)
  - Tool timeout handling (tool_call marked TIMEOUT, task marked FAILED)
  - Runs against in-memory SQLite database.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.agent.executor import Executor
from app.agent.planner import PlanModel, PlanStep
from app.core.errors import ToolError, ToolTimeoutError, ToolUnavailableError
from app.db.models import (
    Base,
    StepStatus,
    Task,
    TaskStatus,
    TaskStep,
    ToolCall,
    ToolCallStatus,
    User,
)
from app.tools.base import Tool
from app.tools.mock_tool import MockTool
from app.tools.registry import ToolRegistry


class FailingTool(Tool):
    @property
    def name(self) -> str:
        return "failing_tool"

    @property
    def description(self) -> str:
        return "Always fails"

    @property
    def input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def execute(self, args: dict[str, Any]) -> str:
        raise ToolUnavailableError(tool_name=self.name)


class TimeoutMockTool(Tool):
    @property
    def name(self) -> str:
        return "timeout_tool"

    @property
    def description(self) -> str:
        return "Always times out"

    @property
    def input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def execute(self, args: dict[str, Any]) -> str:
        raise ToolTimeoutError(tool_name=self.name, timeout_ms=100)


@pytest.fixture
async def db_session():
    """Create in-memory SQLite session with initialized schema and test user."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        user = User(
            id=uuid.uuid4(),
            username="executor_user",
            email="executor@example.com",
            is_active=True,
        )
        session.add(user)
        await session.commit()
        session._test_user_id = user.id

    async with session_factory() as session:
        session._test_user_id = user.id
        yield session

    await engine.dispose()


class TestExecutor:
    @pytest.mark.asyncio
    async def test_sequential_execution_success(self, db_session: AsyncSession) -> None:
        registry = ToolRegistry()
        registry.register(MockTool(response="Output 1"))

        # Create task in DB
        task = Task(
            user_id=db_session._test_user_id,
            goal="Test sequential execution",
            status=TaskStatus.EXECUTING,
        )
        db_session.add(task)
        await db_session.flush()

        plan = PlanModel(
            steps=[
                PlanStep(
                    step_number=1,
                    description="Run first step",
                    tool_name="mock_tool",
                    tool_args={"input": "arg1"},
                ),
                PlanStep(
                    step_number=2,
                    description="Run second step",
                    tool_name="mock_tool",
                    tool_args={"input": "arg2"},
                ),
            ]
        )

        executor = Executor(registry=registry, db=db_session)
        result_text = await executor.execute_plan(task, plan)

        assert "Step 1: Output 1" in result_text
        assert "Step 2: Output 1" in result_text

        # Verify task_steps in DB
        steps_res = await db_session.execute(
            select(TaskStep).where(TaskStep.task_id == task.id).order_by(TaskStep.step_number)
        )
        db_steps = steps_res.scalars().all()
        assert len(db_steps) == 2
        assert db_steps[0].status == StepStatus.COMPLETED.value
        assert db_steps[1].status == StepStatus.COMPLETED.value

        # Verify tool_calls in DB
        calls_res = await db_session.execute(
            select(ToolCall).where(ToolCall.task_id == task.id)
        )
        db_calls = calls_res.scalars().all()
        assert len(db_calls) == 2
        assert db_calls[0].status == ToolCallStatus.SUCCESS.value
        assert db_calls[1].status == ToolCallStatus.SUCCESS.value

    @pytest.mark.asyncio
    async def test_tool_failure_stops_execution(self, db_session: AsyncSession) -> None:
        registry = ToolRegistry()
        registry.register(FailingTool())
        registry.register(MockTool(response="Should not run"))

        task = Task(
            user_id=db_session._test_user_id,
            goal="Test tool failure",
            status=TaskStatus.EXECUTING,
        )
        db_session.add(task)
        await db_session.flush()

        plan = PlanModel(
            steps=[
                PlanStep(
                    step_number=1,
                    description="Failing step",
                    tool_name="failing_tool",
                    tool_args={},
                ),
                PlanStep(
                    step_number=2,
                    description="Second step",
                    tool_name="mock_tool",
                    tool_args={"input": "test"},
                ),
            ]
        )

        executor = Executor(registry=registry, db=db_session)
        with pytest.raises(ToolUnavailableError):
            await executor.execute_plan(task, plan)

        assert task.status == TaskStatus.FAILED
        assert "Step 1 failed" in task.error_message

        # Verify step 2 was never created/executed
        steps_res = await db_session.execute(
            select(TaskStep).where(TaskStep.task_id == task.id)
        )
        db_steps = steps_res.scalars().all()
        assert len(db_steps) == 1
        assert db_steps[0].status == StepStatus.FAILED.value

    @pytest.mark.asyncio
    async def test_tool_timeout_handling(self, db_session: AsyncSession) -> None:
        registry = ToolRegistry()
        registry.register(TimeoutMockTool())

        task = Task(
            user_id=db_session._test_user_id,
            goal="Test timeout handling",
            status=TaskStatus.EXECUTING,
        )
        db_session.add(task)
        await db_session.flush()

        plan = PlanModel(
            steps=[
                PlanStep(
                    step_number=1,
                    description="Timing out step",
                    tool_name="timeout_tool",
                    tool_args={},
                )
            ]
        )

        executor = Executor(registry=registry, db=db_session)
        with pytest.raises(ToolTimeoutError):
            await executor.execute_plan(task, plan)

        assert task.status == TaskStatus.FAILED
        assert "timed out" in task.error_message

        # Verify tool_call marked TIMEOUT
        calls_res = await db_session.execute(
            select(ToolCall).where(ToolCall.task_id == task.id)
        )
        db_call = calls_res.scalar_one()
        assert db_call.status == ToolCallStatus.TIMEOUT.value

    @pytest.mark.asyncio
    async def test_zero_steps_execution(self, db_session: AsyncSession) -> None:
        registry = ToolRegistry()
        task = Task(
            user_id=db_session._test_user_id,
            goal="Test zero steps execution",
            status=TaskStatus.EXECUTING,
        )
        db_session.add(task)
        await db_session.flush()

        plan = PlanModel(steps=[])
        executor = Executor(registry=registry, db=db_session)
        result = await executor.execute_plan(task, plan)

        assert result == []
        assert task.status == TaskStatus.EXECUTING
