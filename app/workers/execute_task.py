"""
app/workers/execute_task.py
===========================
ARQ background worker — the heart of the execution pipeline.

This file is the Week 1 **skeleton**.  The function signature, context
typing, logging, and status-update helpers are all wired up and ready
for the Week 2 LangGraph implementation to drop in.

Week 2 will implement:
  1. Fetch task from DB
  2. Update status → PLANNING
  3. Run LangGraph agent (8 nodes)
  4. Persist result to DB
  5. Update status → COMPLETED / FAILED

How ARQ passes context
  ARQ injects a ``ctx`` dict into every job function as the first argument.
  We attach shared resources (DB session factory, Redis pool, settings) to
  this dict in ``WorkerSettings.on_startup`` (wired in Week 2).
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


# ── Type alias for the ARQ context dict ───────────────────────────────────────
# Week 2: replace Any with a proper TypedDict
ArqContext = dict[str, Any]


# ══════════════════════════════════════════════════════════════════════════════
# Main worker function
# ══════════════════════════════════════════════════════════════════════════════
async def execute_task(ctx: ArqContext, task_id: str) -> dict[str, Any]:
    """Execute a single agent task in the background.

    This function is registered with ARQ and called by the worker process
    whenever a ``execute_task`` job is dequeued from Redis.

    Args:
        ctx:     ARQ context dict (shared resources injected at worker startup).
        task_id: UUID string of the ``tasks`` row to process.

    Returns:
        A dict summarising execution outcome — stored by ARQ and queryable
        via the job ID.
    """
    start_time = time.monotonic()
    logger.info("[execute_task] START | task_id=%s", task_id)

    try:
        # ── Step 1: Fetch task from database ──────────────────────────────
        # Week 2 implementation:
        # db: AsyncSession = ctx["db_session"]
        # task = await db.get(Task, UUID(task_id))
        # if task is None:
        #     logger.error("[execute_task] Task not found | task_id=%s", task_id)
        #     return {"status": "failed", "error": "task_not_found"}
        logger.debug("[execute_task] Step 1: fetch task (stub)")

        # ── Step 2: Mark task as PLANNING ──────────────────────────────────
        # Week 2 implementation:
        # task.status = TaskStatus.PLANNING
        # task.execution_started_at = datetime.now(timezone.utc)
        # await db.commit()
        # await _publish_event(ctx, task_id, "status_change", {"status": "PLANNING"})
        logger.debug("[execute_task] Step 2: status → PLANNING (stub)")

        # ── Step 3: Run LangGraph agent ────────────────────────────────────
        # Week 2 implementation:
        # agent = build_agent_graph()  # from app/agent/graph.py
        # state = AgentState(task_id=task_id, goal=task.goal)
        # result_state = await agent.ainvoke(state, config={"thread_id": task_id})
        logger.debug("[execute_task] Step 3: LangGraph agent (stub)")

        # ── Step 4: Persist result ─────────────────────────────────────────
        # Week 2 implementation:
        # task.status = TaskStatus.COMPLETED
        # task.result = result_state.final_answer
        # task.plan = result_state.plan
        # task.execution_completed_at = datetime.now(timezone.utc)
        # await db.commit()
        logger.debug("[execute_task] Step 4: persist result (stub)")

        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        logger.info(
            "[execute_task] DONE (stub) | task_id=%s elapsed_ms=%d", task_id, elapsed_ms
        )
        return {
            "status": "stub_complete",
            "task_id": task_id,
            "elapsed_ms": elapsed_ms,
        }

    except Exception as exc:
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        logger.exception(
            "[execute_task] FAILED | task_id=%s elapsed_ms=%d error=%s",
            task_id,
            elapsed_ms,
            exc,
        )

        # Week 2 implementation:
        # try:
        #     task.status = TaskStatus.FAILED
        #     task.error_message = str(exc)
        #     await db.commit()
        # except Exception:
        #     logger.exception("[execute_task] Could not update task status to FAILED")

        return {
            "status": "failed",
            "task_id": task_id,
            "error": str(exc),
            "elapsed_ms": elapsed_ms,
        }


# ── Private helpers (stubs for Week 2) ────────────────────────────────────────
async def _publish_event(
    ctx: ArqContext,
    task_id: str,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    """Publish a task event to the Redis Pub/Sub channel.

    Week 2 implementation:
        redis: Redis = ctx["redis"]
        await redis.publish(
            f"task_events:{task_id}",
            json.dumps({"event": event_type, "data": payload}),
        )
    """
    logger.debug(
        "[_publish_event] stub | task_id=%s event=%s payload=%s",
        task_id,
        event_type,
        payload,
    )


async def _update_task_status(
    ctx: ArqContext,
    task_id: str,
    new_status: str,
) -> None:
    """Update the task's status column and publish an SSE event.

    Week 2 implementation: DB update + _publish_event call.
    """
    logger.debug(
        "[_update_task_status] stub | task_id=%s new_status=%s", task_id, new_status
    )
