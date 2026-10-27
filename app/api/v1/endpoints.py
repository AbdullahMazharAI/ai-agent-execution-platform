"""
app/api/v1/endpoints.py
=======================
All 10 REST API endpoints (Phase 3, Week 2 wiring).

Implementation status:
  ✅  POST /tasks         — real DB insert + ARQ enqueue
  ✅  GET  /tasks/{id}    — real DB lookup
  ✅  GET  /tasks         — real paginated list
  ✅  GET  /tasks/{id}/steps  — real task_steps query
  ✅  GET  /tasks/{id}/errors — real errors query
  🔲  POST /tasks/{id}/cancel — Week 4
  🔲  GET  /tasks/{id}/events — Week 4 (SSE)
  🔲  GET  /tasks/{id}/result — Week 4-5
  🔲  POST /tasks/{id}/retry  — Week 4
  🔲  GET  /metrics           — Week 5
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import verify_api_key
from app.core.queue import enqueue_task
from app.database import get_db_session
from app.db.models import Error as ErrorModel, Task, TaskStatus, TaskStep
from app.db.schemas import (
    CancelTaskResponse,
    ErrorListResponse,
    TaskCreateRequest,
    TaskDetailResponse,
    TaskErrorDetail,
    TaskListResponse,
    TaskResponse,
    TaskResultResponse,
    TaskStepResponse,
    TaskStepsResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["tasks"])


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
    """Insert Task row (status PENDING), enqueue execute_task, return 201."""
    logger.info("create_task called | user=%s goal=%r", user_id, request.goal[:80])

    task = Task(
        user_id=user_id,
        goal=request.goal,
        status=TaskStatus.PENDING,
    )
    db.add(task)
    await db.flush()  # Get the ID assigned

    # Enqueue background job
    try:
        await enqueue_task(str(task.id))
    except Exception as exc:
        logger.error("Failed to enqueue task %s: %s", task.id, exc)
        # Task is still in DB with PENDING status — worker can pick it up later

    return TaskResponse(
        task_id=task.id,
        status=task.status.value,
        created_at=task.created_at or datetime.now(timezone.utc),
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
    """SELECT from tasks WHERE id = task_id AND user_id = user_id."""
    logger.info("get_task called | user=%s task=%s", user_id, task_id)

    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.user_id == user_id)
    )
    task = result.scalar_one_or_none()

    if task is None:
        raise HTTPException(status_code=404, detail="Task not found.")

    # Calculate execution time
    execution_time_ms = None
    if task.execution_started_at and task.execution_completed_at:
        delta = task.execution_completed_at - task.execution_started_at
        execution_time_ms = int(delta.total_seconds() * 1000)

    return TaskDetailResponse(
        task_id=task.id,
        user_id=task.user_id,
        goal=task.goal,
        status=task.status.value if isinstance(task.status, TaskStatus) else task.status,
        plan=task.plan,
        result=task.result,
        error_message=task.error_message,
        langgraph_thread_id=task.langgraph_thread_id,
        execution_started_at=task.execution_started_at,
        execution_completed_at=task.execution_completed_at,
        execution_time_ms=execution_time_ms,
        created_at=task.created_at,
        updated_at=task.updated_at,
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
    """Real paginated list for the user."""
    logger.info("list_tasks called | user=%s limit=%d offset=%d", user_id, limit, offset)

    query = select(Task).where(Task.user_id == user_id)
    count_query = select(sa_func.count()).select_from(Task).where(Task.user_id == user_id)

    if status_filter:
        try:
            status_enum = TaskStatus(status_filter)
            query = query.where(Task.status == status_enum)
            count_query = count_query.where(Task.status == status_enum)
        except ValueError:
            pass  # ignore invalid status filter

    query = query.order_by(Task.created_at.desc()).limit(limit).offset(offset)

    result = await db.execute(query)
    tasks = result.scalars().all()

    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    task_details = []
    for t in tasks:
        execution_time_ms = None
        if t.execution_started_at and t.execution_completed_at:
            delta = t.execution_completed_at - t.execution_started_at
            execution_time_ms = int(delta.total_seconds() * 1000)

        task_details.append(TaskDetailResponse(
            task_id=t.id,
            user_id=t.user_id,
            goal=t.goal,
            status=t.status.value if isinstance(t.status, TaskStatus) else t.status,
            plan=t.plan,
            result=t.result,
            error_message=t.error_message,
            langgraph_thread_id=t.langgraph_thread_id,
            execution_started_at=t.execution_started_at,
            execution_completed_at=t.execution_completed_at,
            execution_time_ms=execution_time_ms,
            created_at=t.created_at,
            updated_at=t.updated_at,
        ))

    return TaskListResponse(tasks=task_details, total=total, limit=limit, offset=offset)


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
    """Week 4 stub."""
    logger.info("cancel_task called | user=%s task=%s", user_id, task_id)

    return CancelTaskResponse(
        task_id=task_id,
        status="CANCELLED",
        message="Cancellation requested (stub — Week 4).",
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
    """Week 4 stub."""
    logger.info("task_events_sse called | user=%s task=%s", user_id, task_id)

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
    """Real task_steps rows."""
    logger.info("get_task_steps called | user=%s task=%s", user_id, task_id)

    # Verify task belongs to user
    task_result = await db.execute(
        select(Task.id).where(Task.id == task_id, Task.user_id == user_id)
    )
    if task_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Task not found.")

    result = await db.execute(
        select(TaskStep)
        .where(TaskStep.task_id == task_id)
        .order_by(TaskStep.step_number)
    )
    steps = result.scalars().all()

    step_responses = [
        TaskStepResponse(
            step_id=s.id,
            task_id=s.task_id,
            step_number=s.step_number,
            step_description=s.step_description,
            tool_name=s.tool_name,
            status=s.status,
            result=s.result,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in steps
    ]

    return TaskStepsResponse(steps=step_responses, total=len(step_responses))


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
    """Week 4-5 stub — returns partial data."""
    logger.info("get_task_result called | user=%s task=%s", user_id, task_id)

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
    """Real errors rows."""
    logger.info("get_task_errors called | user=%s task=%s", user_id, task_id)

    # Verify task belongs to user
    task_result = await db.execute(
        select(Task.id).where(Task.id == task_id, Task.user_id == user_id)
    )
    if task_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Task not found.")

    result = await db.execute(
        select(ErrorModel)
        .where(ErrorModel.task_id == task_id)
        .order_by(ErrorModel.created_at)
    )
    errors = result.scalars().all()

    error_details = [
        TaskErrorDetail(
            error_id=e.id,
            task_id=e.task_id,
            step_id=e.step_id,
            error_type=e.error_type.value if hasattr(e.error_type, 'value') else str(e.error_type),
            error_code=e.error_code,
            error_message=e.error_message,
            recovery_action=e.recovery_action,
            created_at=e.created_at,
        )
        for e in errors
    ]

    return ErrorListResponse(errors=error_details, total=len(error_details))


# ══════════════════════════════════════════════════════════════════════════════
# 9. POST /tasks/{task_id}/retry — Retry a failed task
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
    """Week 4 stub."""
    logger.info("retry_task called | user=%s task=%s", user_id, task_id)

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
    """Week 5 stub."""
    return (
        "# HELP agent_platform_up Agent platform is running\n"
        "# TYPE agent_platform_up gauge\n"
        "agent_platform_up 1\n"
    )
