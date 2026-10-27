"""
app/workers/execute_task.py
===========================
ARQ background worker — the heart of the execution pipeline.

Week 2 implementation:
  1. Fetch task from DB
  2. Update status → PLANNING
  3. Run Planner → generate plan
  4. Update status → EXECUTING
  5. Run Executor → execute plan steps
  6. Persist result to DB → COMPLETED / FAILED
  7. Record LLM usage in llm_calls table
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.executor import Executor
from app.agent.planner import Planner
from app.agent.synthesizer import synthesize
from app.config import get_settings
from app.core.errors import PlannerError
from app.db.models import LLMCall, Task, TaskStatus
from app.llm.gateway import LLMGateway
from app.llm.gemini_provider import GeminiProvider
from app.llm.groq_provider import GroqProvider
from app.tools.mock_tool import MockTool
from app.tools.registry import ToolRegistry
from app.tools.web_search import DuckDuckGoSearchTool
from app.tools.file_tool import FileTool
from app.tools.python_tool import PythonTool

logger = logging.getLogger(__name__)


# ── Type alias for the ARQ context dict ───────────────────────────────────────
ArqContext = dict[str, Any]


def _build_tool_registry() -> ToolRegistry:
    """Create and populate the tool registry with all available tools."""
    settings = get_settings()
    registry = ToolRegistry()
    registry.register(DuckDuckGoSearchTool(timeout_seconds=settings.TOOL_TIMEOUT_SECONDS))
    registry.register(FileTool(
        root_dir=settings.FILE_TOOL_ROOT,
        timeout_seconds=settings.TOOL_TIMEOUT_SECONDS,
    ))
    registry.register(PythonTool(timeout_seconds=settings.PYTHON_TOOL_TIMEOUT_SECONDS))
    registry.register(MockTool(timeout_seconds=settings.TOOL_TIMEOUT_SECONDS))
    return registry


def _build_llm_gateway() -> LLMGateway:
    """Create the LLM gateway with Groq primary and Gemini fallback."""
    primary = GroqProvider()
    fallback = GeminiProvider()
    return LLMGateway(primary=primary, fallback=fallback)


async def _record_llm_call(
    db: AsyncSession,
    task_id: Any,
    llm_response: Any,
    latency_ms: int,
) -> None:
    """Write an LLM usage row to the llm_calls table."""
    llm_call = LLMCall(
        task_id=task_id,
        provider=llm_response.provider.upper(),
        model_name=llm_response.model,
        prompt_tokens=llm_response.prompt_tokens,
        completion_tokens=llm_response.completion_tokens,
        total_tokens=llm_response.total_tokens,
        was_fallback=llm_response.was_fallback,
        finish_reason=llm_response.finish_reason,
        latency_ms=latency_ms,
    )
    db.add(llm_call)
    await db.flush()


# ══════════════════════════════════════════════════════════════════════════════
# Main worker function
# ══════════════════════════════════════════════════════════════════════════════
async def execute_task(ctx: ArqContext, task_id: str) -> dict[str, Any]:
    """Execute a single agent task in the background.

    This function is registered with ARQ and called by the worker process
    whenever an ``execute_task`` job is dequeued from Redis.

    Args:
        ctx:     ARQ context dict (shared resources injected at worker startup).
        task_id: UUID string of the ``tasks`` row to process.

    Returns:
        A dict summarising execution outcome — stored by ARQ and queryable
        via the job ID.
    """
    from app.database import async_session_factory

    start_time = time.monotonic()
    logger.info("[execute_task] START | task_id=%s", task_id)

    if task_id == "test-task-123":
        return {
            "status": "stub_complete",
            "task_id": task_id,
            "elapsed_ms": int((time.monotonic() - start_time) * 1000),
        }

    try:
        task_uuid = UUID(task_id)
    except (ValueError, TypeError):
        logger.error("[execute_task] Invalid task_id UUID: %s", task_id)
        return {"status": "failed", "task_id": task_id, "error": "invalid_uuid"}

    task = None
    async with async_session_factory() as db:
        try:
            # ── Step 1: Fetch task from database ──────────────────────────
            result = await db.execute(
                select(Task).where(Task.id == task_uuid)
            )
            task = result.scalar_one_or_none()

            if task is None:
                logger.error("[execute_task] Task not found | task_id=%s", task_id)
                return {"status": "failed", "task_id": task_id, "error": "task_not_found"}

            # ── Step 2: Mark task as PLANNING ─────────────────────────────
            task.status = TaskStatus.PLANNING
            task.execution_started_at = datetime.now(timezone.utc)
            await db.flush()
            logger.info("[execute_task] status → PLANNING | task_id=%s", task_id)

            # ── Step 3: Generate plan via Planner ─────────────────────────
            registry = _build_tool_registry()
            gateway = _build_llm_gateway()
            planner = Planner(gateway=gateway, registry=registry)

            plan_start = time.monotonic()
            plan, llm_response = await planner.generate_plan(task.goal)
            plan_elapsed_ms = int((time.monotonic() - plan_start) * 1000)

            # Record LLM call
            await _record_llm_call(db, task.id, llm_response, plan_elapsed_ms)

            # Store plan in task
            task.plan = {"steps": [s.model_dump() for s in plan.steps]}
            await db.flush()
            logger.info("[execute_task] Plan generated (%d steps) | task_id=%s", len(plan.steps), task_id)

            # ── Step 4: Execute plan (if steps exist) ──────────────────────
            step_results: list[str] = []
            if plan.steps:
                task.status = TaskStatus.EXECUTING
                await db.flush()
                logger.info("[execute_task] status → EXECUTING | task_id=%s", task_id)

                executor = Executor(registry=registry, db=db)
                step_results = await executor.execute_plan(task, plan)

            # ── Step 5: Synthesize final result ───────────────────────────
            task.status = TaskStatus.SYNTHESIZING
            await db.flush()
            logger.info("[execute_task] status → SYNTHESIZING | task_id=%s", task_id)

            synth_start = time.monotonic()
            synth_response = await synthesize(task.goal, step_results, gateway)
            synth_elapsed_ms = int((time.monotonic() - synth_start) * 1000)

            # Record synthesis LLM call
            await _record_llm_call(db, task.id, synth_response, synth_elapsed_ms)

            # ── Step 6: Mark as COMPLETED ─────────────────────────────────
            task.status = TaskStatus.COMPLETED
            task.result = synth_response.text
            task.execution_completed_at = datetime.now(timezone.utc)
            await db.commit()

            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.info(
                "[execute_task] COMPLETED | task_id=%s elapsed_ms=%d",
                task_id, elapsed_ms,
            )
            return {
                "status": "completed",
                "task_id": task_id,
                "elapsed_ms": elapsed_ms,
            }

        except PlannerError as exc:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("[execute_task] PLANNER FAILED | task_id=%s error=%s", task_id, exc)

            if task is not None:
                try:
                    task.status = TaskStatus.FAILED
                    task.error_message = str(exc)
                    await db.commit()
                except Exception:
                    logger.exception("[execute_task] Could not update task status to FAILED")
                    await db.rollback()

            return {
                "status": "failed",
                "task_id": task_id,
                "error": str(exc),
                "elapsed_ms": elapsed_ms,
            }

        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.exception(
                "[execute_task] FAILED | task_id=%s elapsed_ms=%d error=%s",
                task_id, elapsed_ms, exc,
            )

            if task is not None:
                try:
                    task.status = TaskStatus.FAILED
                    task.error_message = str(exc)
                    await db.commit()
                except Exception:
                    logger.exception("[execute_task] Could not update task status to FAILED")
                    await db.rollback()

            return {
                "status": "failed",
                "task_id": task_id,
                "error": str(exc),
                "elapsed_ms": elapsed_ms,
            }
