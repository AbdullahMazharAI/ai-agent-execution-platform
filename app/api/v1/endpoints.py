"""
app/api/v1/endpoints.py
=======================
All 10 REST API endpoints (Phase 3).

Implementation status (Week 1):
  ✅  Endpoint structure + routing
  ✅  Request / response schemas wired
  ✅  Auth dependency on every endpoint
  🔲  DB reads/writes        → Week 2
  🔲  ARQ task enqueueing    → Week 2
  🔲  SSE streaming          → Week 4
  🔲  Cancellation flag      → Week 4
  🔲  Prometheus metrics     → Week 5
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import verify_api_key
from app.database import get_db_session
from app.db.schemas import (
    CancelTaskResponse,
    ErrorListResponse,
    TaskCreateRequest,
    TaskDetailResponse,
    TaskListResponse,
    TaskResponse,
    TaskResultResponse,
    TaskStepResponse,
    TaskStepsResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["tasks"])

# ── Placeholder sentinel ───────────────────────────────────────────────────────
_MOCK_TASK_ID = UUID("550e8400-e29b-41d4-a716-446655440000")
_MOCK_USER_ID = UUID("550e8400-e29b-41d4-a716-446655440000")
_NOW = "2026-10-11T14:21:50Z"


# ══════════════════════════════════════════════════════════════════════════════
# 1. POST /tasks — Submit a new task
# ══════════════════════════════════════════════════════════════════════════════
@router.post(
    "/tasks",
    status_code=status.HTTP_201_CREATED,
    response_model=TaskResponse,
    summary="Submit a new task",
    description=(
        "Submit a high-level goal. The system queues it for background "
        "execution and immediately returns a task ID."
    ),
)
async def create_task(
    request: TaskCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    user_id: UUID = Depends(verify_api_key),
) -> TaskResponse:
    """Phase 3 — Endpoint 1.

    Week 2 TODO:
      1. INSERT into ``tasks`` table with status=PENDING.
      2. Enqueue ``execute_task`` job to ARQ with the new task_id.
      3. Return real task_id and created_at from the DB row.
    """
    logger.info("create_task called | user=%s goal=%r", user_id, request.goal[:80])

    # --- Stub (Week 1) ---
    return TaskResponse(
        task_id=_MOCK_TASK_ID,
        status="PENDING",
        created_at=datetime.now(timezone.utc),
    )


# ══════════════════════════════════════════════════════════════════════════════
# 2. GET /tasks/{task_id} — Get task details
# ══════════════════════════════════════════════════════════════════════════════
@router.get(
    "/tasks/{task_id}",
    response_model=TaskDetailResponse,
    summary="Get task details",
    description="Return full task state including plan, result, and timing.",
)
async def get_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    user_id: UUID = Depends(verify_api_key),
) -> TaskDetailResponse:
    """Phase 3 — Endpoint 2.

    Week 2 TODO:
      1. SELECT from ``tasks`` WHERE id = task_id AND user_id = user_id.
      2. Raise 404 if not found.
      3. Calculate execution_time_ms from timestamps.
      4. Return full TaskDetailResponse.
    """
    logger.info("get_task called | user=%s task=%s", user_id, task_id)

    # --- Stub (Week 1) ---
    now = datetime.now(timezone.utc)
    return TaskDetailResponse(
        task_id=task_id,
        user_id=user_id,
        goal="Example task (stub)",
        status="PENDING",
        plan=None,
        result=None,
        error_message=None,
        langgraph_thread_id=None,
        execution_started_at=None,
        execution_completed_at=None,
        execution_time_ms=None,
        created_at=now,
        updated_at=now,
    )


# ══════════════════════════════════════════════════════════════════════════════
# 3. GET /tasks — List tasks (paginated)
# ══════════════════════════════════════════════════════════════════════════════
@router.get(
    "/tasks",
    response_model=TaskListResponse,
    summary="List tasks",
    description="Return a paginated list of the authenticated user's tasks.",
)
async def list_tasks(
    limit: int = Query(default=10, ge=1, le=100, description="Max results to return"),
    offset: int = Query(default=0, ge=0, description="Number of results to skip"),
    status_filter: str | None = Query(default=None, alias="status", description="Filter by status"),
    db: AsyncSession = Depends(get_db_session),
    user_id: UUID = Depends(verify_api_key),
) -> TaskListResponse:
    """Phase 3 — Endpoint 3.

    Week 2 TODO:
      1. SELECT from ``tasks`` WHERE user_id = user_id [AND status = filter]
         ORDER BY created_at DESC LIMIT limit OFFSET offset.
      2. SELECT COUNT(*) for total.
      3. Return TaskListResponse with real data.
    """
    logger.info("list_tasks called | user=%s limit=%d offset=%d", user_id, limit, offset)

    # --- Stub (Week 1) ---
    return TaskListResponse(tasks=[], total=0, limit=limit, offset=offset)


# ══════════════════════════════════════════════════════════════════════════════
# 4. POST /tasks/{task_id}/cancel — Cancel a running task
# ══════════════════════════════════════════════════════════════════════════════
@router.post(
    "/tasks/{task_id}/cancel",
    response_model=CancelTaskResponse,
    summary="Cancel a running task",
    description=(
        "Requests graceful cancellation. The agent checks a Redis flag between "
        "nodes and exits cleanly."
    ),
)
async def cancel_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    user_id: UUID = Depends(verify_api_key),
) -> CancelTaskResponse:
    """Phase 3 — Endpoint 4.

    Week 4 TODO:
      1. Verify task belongs to user_id; raise 404/403 otherwise.
      2. Verify task is in a cancellable state (PENDING/PLANNING/EXECUTING).
      3. Set Redis key  ``cancel:{task_id}`` = "1"  with TTL 3600s.
      4. Update task status to CANCELLED in DB.
    """
    logger.info("cancel_task called | user=%s task=%s", user_id, task_id)

    # --- Stub (Week 1) ---
    return CancelTaskResponse(
        task_id=task_id,
        status="CANCELLED",
        message="Cancellation requested (stub).",
    )


# ══════════════════════════════════════════════════════════════════════════════
# 5. GET /tasks/{task_id}/events — SSE real-time stream
# ══════════════════════════════════════════════════════════════════════════════
@router.get(
    "/tasks/{task_id}/events",
    summary="SSE event stream",
    description=(
        "Server-Sent Events stream. Returns real-time status updates as the "
        "agent executes the task."
    ),
)
async def task_events_sse(
    task_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    user_id: UUID = Depends(verify_api_key),
):
    """Phase 3 — Endpoint 5.

    Week 4 TODO:
      1. Verify task belongs to user_id.
      2. Subscribe to Redis Pub/Sub channel  ``task_events:{task_id}``.
      3. Yield ``EventSourceResponse`` wrapping the async generator.
      4. Send a final ``done`` event when task reaches terminal state.
    """
    logger.info("task_events_sse called | user=%s task=%s", user_id, task_id)

    # --- Stub (Week 1) ---
    # Real implementation: return EventSourceResponse(generator)
    return PlainTextResponse(
        content=(
            f"data: {{\"task_id\": \"{task_id}\", \"status\": \"stub\"}}\n\n"
        ),
        media_type="text/event-stream",
    )


# ══════════════════════════════════════════════════════════════════════════════
# 6. GET /tasks/{task_id}/steps — Execution steps
# ══════════════════════════════════════════════════════════════════════════════
@router.get(
    "/tasks/{task_id}/steps",
    response_model=TaskStepsResponse,
    summary="Get execution steps",
    description="Return all planned and executed steps for the task.",
)
async def get_task_steps(
    task_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    user_id: UUID = Depends(verify_api_key),
) -> TaskStepsResponse:
    """Phase 3 — Endpoint 6.

    Week 3 TODO:
      1. Verify task belongs to user_id.
      2. SELECT from ``task_steps`` WHERE task_id = task_id ORDER BY step_number.
      3. Return TaskStepsResponse.
    """
    logger.info("get_task_steps called | user=%s task=%s", user_id, task_id)

    # --- Stub (Week 1) ---
    return TaskStepsResponse(steps=[], total=0)


# ══════════════════════════════════════════════════════════════════════════════
# 7. GET /tasks/{task_id}/result — Final result + verification + metrics
# ══════════════════════════════════════════════════════════════════════════════
@router.get(
    "/tasks/{task_id}/result",
    response_model=TaskResultResponse,
    summary="Get task result",
    description=(
        "Return the final result, verification report, and resource-usage "
        "metrics. Only meaningful once the task is COMPLETED."
    ),
)
async def get_task_result(
    task_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    user_id: UUID = Depends(verify_api_key),
) -> TaskResultResponse:
    """Phase 3 — Endpoint 7.

    Week 4 TODO:
      1. Verify task belongs to user_id.
      2. JOIN tasks + verification_runs + usage_metrics.
      3. Raise 404 if task not found; 409 if not yet COMPLETED.
      4. Return full TaskResultResponse.
    """
    logger.info("get_task_result called | user=%s task=%s", user_id, task_id)

    # --- Stub (Week 1) ---
    return TaskResultResponse(
        task_id=task_id,
        status="PENDING",
        result=None,
        verification=None,
        metrics=None,
    )


# ══════════════════════════════════════════════════════════════════════════════
# 8. GET /tasks/{task_id}/errors — Error log
# ══════════════════════════════════════════════════════════════════════════════
@router.get(
    "/tasks/{task_id}/errors",
    response_model=ErrorListResponse,
    summary="Get error log",
    description="Return all structured error records for the task.",
)
async def get_task_errors(
    task_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    user_id: UUID = Depends(verify_api_key),
) -> ErrorListResponse:
    """Phase 3 — Endpoint 8.

    Week 3 TODO:
      1. Verify task belongs to user_id.
      2. SELECT from ``errors`` WHERE task_id = task_id ORDER BY created_at.
      3. Return ErrorListResponse.
    """
    logger.info("get_task_errors called | user=%s task=%s", user_id, task_id)

    # --- Stub (Week 1) ---
    return ErrorListResponse(errors=[], total=0)


# ══════════════════════════════════════════════════════════════════════════════
# 9. GET /tasks/{task_id}/retry — Retry a failed task
# ══════════════════════════════════════════════════════════════════════════════
@router.post(
    "/tasks/{task_id}/retry",
    response_model=TaskResponse,
    summary="Retry a failed task",
    description="Re-queue a FAILED task for another execution attempt.",
)
async def retry_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    user_id: UUID = Depends(verify_api_key),
) -> TaskResponse:
    """Phase 3 — Endpoint 9.

    Week 4 TODO:
      1. Verify task belongs to user_id and is in FAILED state.
      2. Reset task status to PENDING, clear error_message.
      3. Re-enqueue to ARQ.
    """
    logger.info("retry_task called | user=%s task=%s", user_id, task_id)

    # --- Stub (Week 1) ---
    return TaskResponse(
        task_id=task_id,
        status="PENDING",
        created_at=datetime.now(timezone.utc),
    )


# ══════════════════════════════════════════════════════════════════════════════
# 10. GET /metrics — Prometheus scrape endpoint
# ══════════════════════════════════════════════════════════════════════════════
@router.get(
    "/metrics",
    response_class=PlainTextResponse,
    summary="Prometheus metrics",
    description=(
        "Prometheus text-format scrape endpoint. "
        "Full instrumentation added in Week 5."
    ),
    tags=["observability"],
)
async def prometheus_metrics() -> str:
    """Phase 3 — Endpoint 10.

    Week 5 TODO:
      1. Import ``prometheus_client.generate_latest``.
      2. Return ``generate_latest(REGISTRY)`` with content-type
         ``text/plain; version=0.0.4; charset=utf-8``.
    """
    # --- Stub (Week 1) ---
    return (
        "# HELP agent_platform_up Agent platform is running\n"
        "# TYPE agent_platform_up gauge\n"
        "agent_platform_up 1\n"
    )
