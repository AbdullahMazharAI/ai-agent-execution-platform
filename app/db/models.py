"""
app/db/models.py
================
SQLAlchemy ORM models matching the Phase 2 database schema exactly.
Using modern SQLAlchemy 2.0 type-annotated mapped syntax (Mapped and mapped_column).

Table inventory (9 tables):
  1.  users
  2.  api_keys
  3.  tasks
  4.  task_steps
  5.  tool_calls
  6.  llm_calls
  7.  errors
  8.  verification_runs
  9.  usage_metrics
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum as PyEnum
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


# Register SQLite compilation overrides for PostgreSQL-specific types so tests can run on SQLite
@compiles(UUID, "sqlite")
def _compile_uuid_sqlite(type_, compiler, **kw):
    return "CHAR(36)"


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    return "TEXT"


# ── Base ───────────────────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    """Modern SQLAlchemy 2.x declarative base."""

    def __init__(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)
        for col in self.__table__.columns:
            if col.name not in kwargs and col.default is not None:
                arg = col.default.arg
                if callable(arg):
                    try:
                        arg = arg(None)
                    except TypeError:
                        arg = arg()
                setattr(self, col.name, arg)


# ── Python-side Enums ──────────────────────────────────────────────────────────
class TaskStatus(str, PyEnum):
    PENDING = "PENDING"
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    SYNTHESIZING = "SYNTHESIZING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    RETRYING = "RETRYING"


class APIKeyStatus(str, PyEnum):
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


class ErrorType(str, PyEnum):
    TRANSIENT = "TRANSIENT"
    LLM_RATE_LIMITED = "LLM_RATE_LIMITED"
    TOOL_UNAVAILABLE = "TOOL_UNAVAILABLE"
    INVALID_INPUT = "INVALID_INPUT"
    TIMEOUT = "TIMEOUT"
    PERMANENT = "PERMANENT"


class StepStatus(str, PyEnum):
    PENDING = "PENDING"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ToolCallStatus(str, PyEnum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"


# ── SQLAlchemy Enum types (reused across models) ───────────────────────────────
_task_status_enum = Enum(
    TaskStatus, name="task_status", create_constraint=True, validate_strings=True
)
_api_key_status_enum = Enum(
    APIKeyStatus, name="api_key_status", create_constraint=True, validate_strings=True
)
_error_type_enum = Enum(
    ErrorType, name="error_type", create_constraint=True, validate_strings=True
)


# ── Models ─────────────────────────────────────────────────────────────────────


class User(Base):
    """Platform user account."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, insert_default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    api_keys: Mapped[list["APIKey"]] = relationship("APIKey", back_populates="user", lazy="select")
    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="user", lazy="select")

    __table_args__ = (
        UniqueConstraint("username", name="uq_users_username"),
        UniqueConstraint("email", name="uq_users_email"),
        Index("idx_users_email", "email"),
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r}>"


class APIKey(Base):
    """Hashed API key associated with a user."""

    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False)   # SHA-256 hex digest
    key_prefix: Mapped[str] = mapped_column(String(8), nullable=False)   # First 8 chars for display (e.g. "sk-ab12")
    status: Mapped[APIKeyStatus] = mapped_column(
        _api_key_status_enum, nullable=False, default=APIKeyStatus.ACTIVE, insert_default=APIKeyStatus.ACTIVE
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="api_keys")

    __table_args__ = (
        UniqueConstraint("key_hash", name="uq_api_keys_key_hash"),
        # Partial index: only active keys need fast lookup by hash
        Index(
            "idx_api_keys_active_lookup",
            "key_hash",
            postgresql_where="status = 'ACTIVE'",
        ),
        Index("idx_api_keys_user_id", "user_id"),
    )

    def __repr__(self) -> str:
        return f"<APIKey prefix={self.key_prefix!r} status={self.status}>"


class Task(Base):
    """Core task entity — represents one user-submitted goal."""

    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[TaskStatus] = mapped_column(
        _task_status_enum, nullable=False, default=TaskStatus.PENDING, insert_default=TaskStatus.PENDING
    )

    # LangGraph / execution state
    plan: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(JSONB, nullable=True)  # Generated execution plan
    result: Mapped[str | None] = mapped_column(Text, nullable=True)                         # Final answer
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    langgraph_thread_id: Mapped[str | None] = mapped_column(String(255), nullable=True)    # Crash-recovery checkpoint

    # Timing
    execution_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    execution_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="tasks")
    steps: Mapped[list["TaskStep"]] = relationship(
        "TaskStep", back_populates="task", cascade="all, delete-orphan"
    )
    tool_calls: Mapped[list["ToolCall"]] = relationship(
        "ToolCall", back_populates="task", cascade="all, delete-orphan"
    )
    llm_calls: Mapped[list["LLMCall"]] = relationship(
        "LLMCall", back_populates="task", cascade="all, delete-orphan"
    )
    errors: Mapped[list["Error"]] = relationship(
        "Error", back_populates="task", cascade="all, delete-orphan"
    )
    verification: Mapped["VerificationRun | None"] = relationship(
        "VerificationRun", uselist=False, back_populates="task", cascade="all, delete-orphan"
    )
    usage_metrics: Mapped["UsageMetrics | None"] = relationship(
        "UsageMetrics", uselist=False, back_populates="task", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_tasks_user_status", "user_id", "status"),
        Index("idx_tasks_created_at", "created_at"),
        Index("idx_tasks_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<Task id={self.id} status={self.status} goal={self.goal[:40]!r}>"


class TaskStep(Base):
    """Individual step within a task's execution plan."""

    __tablename__ = "task_steps"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    step_description: Mapped[str] = mapped_column(Text, nullable=False)
    tool_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=StepStatus.PENDING.value, insert_default=StepStatus.PENDING.value
    )
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    task: Mapped["Task"] = relationship("Task", back_populates="steps")
    tool_calls: Mapped[list["ToolCall"]] = relationship("ToolCall", back_populates="step")
    errors: Mapped[list["Error"]] = relationship("Error", back_populates="step")

    __table_args__ = (
        Index("idx_task_steps_task_id", "task_id"),
        UniqueConstraint("task_id", "step_number", name="uq_task_steps_task_step_num"),
    )

    def __repr__(self) -> str:
        return f"<TaskStep task={self.task_id} step={self.step_number} status={self.status}>"


class ToolCall(Base):
    """Record of every tool invocation during task execution."""

    __tablename__ = "tool_calls"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    step_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("task_steps.id", ondelete="SET NULL"),
        nullable=True,
    )
    tool_name: Mapped[str] = mapped_column(String(255), nullable=False)
    input_args: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, insert_default=dict)
    output: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=ToolCallStatus.PENDING.value, insert_default=ToolCallStatus.PENDING.value
    )
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, insert_default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    task: Mapped["Task"] = relationship("Task", back_populates="tool_calls")
    step: Mapped["TaskStep | None"] = relationship("TaskStep", back_populates="tool_calls")

    __table_args__ = (
        Index("idx_tool_calls_task_id", "task_id"),
        Index("idx_tool_calls_step_id", "step_id"),
    )

    def __repr__(self) -> str:
        return f"<ToolCall tool={self.tool_name!r} status={self.status}>"


class LLMCall(Base):
    """Audit record for every LLM inference request made during execution."""

    __tablename__ = "llm_calls"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)        # GROQ | GEMINI | OLLAMA
    model_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0, insert_default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0, insert_default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0, insert_default=0)
    was_fallback: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, insert_default=False)
    finish_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)    # stop | length | tool_calls
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    task: Mapped["Task"] = relationship("Task", back_populates="llm_calls")

    __table_args__ = (
        Index("idx_llm_calls_task_id", "task_id"),
        Index("idx_llm_calls_provider", "provider"),
    )

    def __repr__(self) -> str:
        return (
            f"<LLMCall provider={self.provider!r} tokens={self.total_tokens} "
            f"fallback={self.was_fallback}>"
        )


class Error(Base):
    """Structured error log entry for a task (or a specific step)."""

    __tablename__ = "errors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    step_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("task_steps.id", ondelete="SET NULL"),
        nullable=True,
    )
    error_type: Mapped[ErrorType] = mapped_column(_error_type_enum, nullable=False)
    error_code: Mapped[str] = mapped_column(String(50), nullable=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    recovery_action: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    task: Mapped["Task"] = relationship("Task", back_populates="errors")
    step: Mapped["TaskStep | None"] = relationship("TaskStep", back_populates="errors")

    __table_args__ = (
        Index("idx_errors_task_id", "task_id"),
        Index("idx_errors_error_type", "error_type"),
    )

    def __repr__(self) -> str:
        return f"<Error type={self.error_type} code={self.error_code!r}>"


class VerificationRun(Base):
    """Result of the LangGraph verification node for a completed task."""

    __tablename__ = "verification_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    # Individual verification checks (Phase 4)
    section_completeness: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, insert_default=False)
    json_validity: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, insert_default=False)
    step_completion: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, insert_default=False)
    truncation_check: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, insert_default=False)
    hallucination_check: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, insert_default=False)
    # Aggregated flag: True iff all checks pass
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, insert_default=False)
    verification_issues: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)  # List[str] of issue descriptions
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1, insert_default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    task: Mapped["Task"] = relationship("Task", back_populates="verification")

    __table_args__ = (
        UniqueConstraint("task_id", name="uq_verification_runs_task_id"),
        Index("idx_verification_runs_task_id", "task_id"),
    )

    def __repr__(self) -> str:
        return f"<VerificationRun task={self.task_id} passed={self.passed}>"


class UsageMetrics(Base):
    """Aggregated resource-usage summary for a completed task."""

    __tablename__ = "usage_metrics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    total_tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0, insert_default=0)
    estimated_cost: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=6), nullable=False, default=Decimal("0.0"), insert_default=Decimal("0.0")
    )
    execution_time_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0, insert_default=0)
    tool_calls_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, insert_default=0)
    llm_calls_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, insert_default=0)
    retries_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, insert_default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    task: Mapped["Task"] = relationship("Task", back_populates="usage_metrics")

    __table_args__ = (
        UniqueConstraint("task_id", name="uq_usage_metrics_task_id"),
        Index("idx_usage_metrics_task_id", "task_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<UsageMetrics task={self.task_id} tokens={self.total_tokens_used} "
            f"cost={self.estimated_cost}>"
        )
