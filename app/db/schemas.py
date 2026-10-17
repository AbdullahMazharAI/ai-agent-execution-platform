"""
app/db/schemas.py
=================
Pydantic v2 request / response schemas for the REST API (Phase 3).

Naming convention:
  *Request  — inbound payload validated by FastAPI
  *Response — outbound payload serialised to JSON
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ── Shared config ──────────────────────────────────────────────────────────────
class _Base(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# ── Task ───────────────────────────────────────────────────────────────────────
class TaskCreateRequest(_Base):
    """POST /api/v1/tasks request body."""

    goal: str = Field(
        ...,
        min_length=1,
        max_length=4096,
        description="The high-level goal for the agent to accomplish.",
        examples=["Compare Python vs JavaScript for AI development"],
    )


class TaskResponse(_Base):
    """Minimal task response returned on creation (201)."""

    task_id: UUID
    status: str
    created_at: datetime


class TaskDetailResponse(_Base):
    """Full task detail returned by GET /api/v1/tasks/{task_id}."""

    task_id: UUID
    user_id: UUID
    goal: str
    status: str
    plan: Optional[dict[str, Any]] = None
    result: Optional[str] = None
    error_message: Optional[str] = None
    langgraph_thread_id: Optional[str] = None
    execution_started_at: Optional[datetime] = None
    execution_completed_at: Optional[datetime] = None
    execution_time_ms: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class TaskListResponse(_Base):
    """Paginated list of tasks."""

    tasks: list[TaskDetailResponse]
    total: int
    limit: int
    offset: int


class TaskStepResponse(_Base):
    """Single step within a task's execution plan."""

    step_id: UUID
    task_id: UUID
    step_number: int
    step_description: str
    tool_name: Optional[str] = None
    status: str
    result: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class TaskStepsResponse(_Base):
    """Collection of steps for GET /api/v1/tasks/{task_id}/steps."""

    steps: list[TaskStepResponse]
    total: int


# ── Verification ───────────────────────────────────────────────────────────────
class VerificationResult(_Base):
    """Outcome of the verification node."""

    passed: bool
    section_completeness: bool
    json_validity: bool
    step_completion: bool
    truncation_check: bool
    hallucination_check: bool
    issues: list[str] = Field(default_factory=list)
    attempt_count: int


# ── Usage Metrics ──────────────────────────────────────────────────────────────
class UsageMetricsResponse(_Base):
    """Resource consumption summary for a task."""

    total_tokens_used: int
    estimated_cost: Decimal
    execution_time_ms: int
    tool_calls_count: int
    llm_calls_count: int
    retries_count: int


# ── Task Result ────────────────────────────────────────────────────────────────
class TaskResultResponse(_Base):
    """Full result payload for GET /api/v1/tasks/{task_id}/result."""

    task_id: UUID
    status: str
    result: Optional[str] = None
    verification: Optional[VerificationResult] = None
    metrics: Optional[UsageMetricsResponse] = None


# ── Errors ─────────────────────────────────────────────────────────────────────
class TaskErrorDetail(_Base):
    """Single error entry."""

    error_id: UUID
    task_id: UUID
    step_id: Optional[UUID] = None
    error_type: str
    error_code: str
    error_message: str
    recovery_action: Optional[str] = None
    created_at: datetime


class ErrorListResponse(_Base):
    """Error log for GET /api/v1/tasks/{task_id}/errors."""

    errors: list[TaskErrorDetail]
    total: int


# ── Generic / misc ─────────────────────────────────────────────────────────────
class CancelTaskResponse(_Base):
    """Response for POST /api/v1/tasks/{task_id}/cancel."""

    task_id: UUID
    status: str
    message: str


class ErrorResponse(_Base):
    """Standard error response body."""

    error: str
    detail: str


class HealthResponse(_Base):
    """GET /health response."""

    status: str
    environment: str
    version: str
    timestamp: datetime
