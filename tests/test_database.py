"""
tests/test_database.py
======================
Database model tests — Week 1 foundation.

These tests verify:
  - ORM model instantiation (no DB required)
  - Enum value correctness
  - Default field values
  - Relationship attribute names
  - Repr strings

Week 2 will add integration tests using an in-memory SQLite or a
test-dedicated PostgreSQL database (via pytest-asyncio + sqlalchemy fixtures).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.db.models import (
    APIKey,
    APIKeyStatus,
    Error,
    ErrorType,
    LLMCall,
    StepStatus,
    Task,
    TaskStatus,
    TaskStep,
    ToolCall,
    ToolCallStatus,
    UsageMetrics,
    User,
    VerificationRun,
)


# ══════════════════════════════════════════════════════════════════════════════
# Enum value correctness
# ══════════════════════════════════════════════════════════════════════════════
class TestEnums:
    def test_task_status_values(self) -> None:
        expected = {
            "PENDING", "PLANNING", "EXECUTING", "VERIFYING",
            "COMPLETED", "FAILED", "CANCELLED", "RETRYING",
        }
        assert {s.value for s in TaskStatus} == expected

    def test_api_key_status_values(self) -> None:
        assert {s.value for s in APIKeyStatus} == {"ACTIVE", "REVOKED", "EXPIRED"}

    def test_error_type_values(self) -> None:
        expected = {
            "TRANSIENT", "LLM_RATE_LIMITED", "TOOL_UNAVAILABLE",
            "INVALID_INPUT", "TIMEOUT", "PERMANENT",
        }
        assert {e.value for e in ErrorType} == expected

    def test_step_status_values(self) -> None:
        assert {s.value for s in StepStatus} == {"PENDING", "EXECUTING", "COMPLETED", "FAILED"}

    def test_tool_call_status_values(self) -> None:
        assert {s.value for s in ToolCallStatus} == {"PENDING", "SUCCESS", "FAILED", "TIMEOUT"}


# ══════════════════════════════════════════════════════════════════════════════
# Model instantiation and defaults
# ══════════════════════════════════════════════════════════════════════════════
class TestUserModel:
    def test_create_user(self) -> None:
        user = User(username="alice", email="alice@example.com")
        assert user.username == "alice"
        assert user.email == "alice@example.com"
        assert user.is_active is True  # default

    def test_user_repr(self) -> None:
        user = User(username="alice", email="alice@example.com")
        user.id = uuid.uuid4()
        assert "alice" in repr(user)


class TestAPIKeyModel:
    def test_create_api_key(self) -> None:
        key = APIKey(
            user_id=uuid.uuid4(),
            key_hash="a" * 64,
            key_prefix="sk-ab12",
        )
        assert key.status == APIKeyStatus.ACTIVE  # default
        assert key.expires_at is None

    def test_api_key_repr(self) -> None:
        key = APIKey(key_prefix="sk-ab12", status=APIKeyStatus.ACTIVE)
        assert "sk-ab12" in repr(key)


class TestTaskModel:
    def test_create_task(self) -> None:
        task = Task(
            user_id=uuid.uuid4(),
            goal="Compare Python vs JavaScript",
        )
        assert task.goal == "Compare Python vs JavaScript"
        assert task.status == TaskStatus.PENDING  # default
        assert task.plan is None
        assert task.result is None

    def test_task_repr_truncates_goal(self) -> None:
        long_goal = "x" * 100
        task = Task(user_id=uuid.uuid4(), goal=long_goal)
        task.id = uuid.uuid4()
        r = repr(task)
        # repr truncates goal at 40 chars
        assert len(r) < 200

    def test_task_relationships_exist(self) -> None:
        """All relationship attributes should be accessible on the class."""
        for attr in ("steps", "tool_calls", "llm_calls", "errors", "verification", "usage_metrics"):
            assert hasattr(Task, attr), f"Task.{attr} relationship missing"


class TestTaskStepModel:
    def test_create_step(self) -> None:
        step = TaskStep(
            task_id=uuid.uuid4(),
            step_number=1,
            step_description="Search the web for Python AI libraries",
        )
        assert step.step_number == 1
        assert step.status == StepStatus.PENDING.value


class TestToolCallModel:
    def test_create_tool_call(self) -> None:
        call = ToolCall(
            task_id=uuid.uuid4(),
            tool_name="duckduckgo_search",
            input_args={"query": "Python AI"},
        )
        assert call.tool_name == "duckduckgo_search"
        assert call.status == ToolCallStatus.PENDING.value
        assert call.retry_count == 0


class TestLLMCallModel:
    def test_create_llm_call(self) -> None:
        call = LLMCall(
            task_id=uuid.uuid4(),
            provider="GROQ",
            prompt_tokens=100,
            completion_tokens=200,
            total_tokens=300,
        )
        assert call.provider == "GROQ"
        assert call.was_fallback is False


class TestErrorModel:
    def test_create_error(self) -> None:
        error = Error(
            task_id=uuid.uuid4(),
            error_type=ErrorType.TRANSIENT,
            error_code="CONNECTION_RESET",
            error_message="Connection reset by peer",
        )
        assert error.error_type == ErrorType.TRANSIENT
        assert error.recovery_action is None


class TestVerificationRunModel:
    def test_create_verification_run(self) -> None:
        vr = VerificationRun(task_id=uuid.uuid4())
        assert vr.passed is False  # default
        assert vr.attempt_count == 1

    def test_all_checks_default_false(self) -> None:
        vr = VerificationRun(task_id=uuid.uuid4())
        for attr in (
            "section_completeness",
            "json_validity",
            "step_completion",
            "truncation_check",
            "hallucination_check",
        ):
            assert getattr(vr, attr) is False, f"VerificationRun.{attr} should default to False"


class TestUsageMetricsModel:
    def test_create_usage_metrics(self) -> None:
        metrics = UsageMetrics(task_id=uuid.uuid4())
        assert metrics.total_tokens_used == 0
        assert metrics.execution_time_ms == 0
        assert metrics.tool_calls_count == 0
        assert metrics.llm_calls_count == 0
        assert metrics.retries_count == 0


# ══════════════════════════════════════════════════════════════════════════════
# Table name constants
# ══════════════════════════════════════════════════════════════════════════════
class TestTableNames:
    @pytest.mark.parametrize("model, expected_table", [
        (User, "users"),
        (APIKey, "api_keys"),
        (Task, "tasks"),
        (TaskStep, "task_steps"),
        (ToolCall, "tool_calls"),
        (LLMCall, "llm_calls"),
        (Error, "errors"),
        (VerificationRun, "verification_runs"),
        (UsageMetrics, "usage_metrics"),
    ])
    def test_table_name(self, model, expected_table: str) -> None:
        assert model.__tablename__ == expected_table
