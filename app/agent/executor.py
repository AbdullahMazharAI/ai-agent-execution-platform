"""
app/agent/executor.py
=====================
Sequential plan executor — runs plan steps one by one using the ToolRegistry.

Records tool_calls and task_steps rows in the database for each invocation.
On any failure, stops execution and marks the task as FAILED.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.planner import PlanModel
from app.core.errors import (
    InvalidInputError,
    ToolError,
    ToolTimeoutError,
    ToolUnavailableError,
)
from app.db.models import (
    StepStatus,
    Task,
    TaskStatus,
    TaskStep,
    ToolCall,
    ToolCallStatus,
)
from app.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class Executor:
    """Execute a plan's steps sequentially using the tool registry.

    Args:
        registry: ToolRegistry with all tools registered.
        db:       Async database session for writing results.
    """

    def __init__(self, registry: ToolRegistry, db: AsyncSession) -> None:
        self._registry = registry
        self._db = db

    async def execute_plan(self, task: Task, plan: PlanModel) -> list[str]:
        """Execute all steps in the plan, updating the database as we go.

        Args:
            task: The Task ORM object to update.
            plan: The validated PlanModel with steps.

        Returns:
            List of step results. Returns empty list if plan has zero steps.

        Raises:
            ToolError subclasses on step failure (after recording to DB).
        """
        if not plan.steps:
            return []

        results: list[str] = []

        for step_def in plan.steps:
            step_start = time.monotonic()

            # Create task_step row
            task_step = TaskStep(
                task_id=task.id,
                step_number=step_def.step_number,
                step_description=step_def.description,
                tool_name=step_def.tool_name,
                status=StepStatus.EXECUTING.value,
            )
            self._db.add(task_step)
            await self._db.flush()  # Get the step ID

            # Create tool_call row
            tool_call = ToolCall(
                task_id=task.id,
                step_id=task_step.id,
                tool_name=step_def.tool_name,
                input_args=step_def.tool_args,
                status=ToolCallStatus.PENDING.value,
            )
            self._db.add(tool_call)
            await self._db.flush()

            try:
                # Get and run the tool
                tool = self._registry.get(step_def.tool_name)
                result = await tool.run(step_def.tool_args)

                elapsed_ms = int((time.monotonic() - step_start) * 1000)

                # Update records
                tool_call.status = ToolCallStatus.SUCCESS.value
                tool_call.output = result
                tool_call.latency_ms = elapsed_ms

                task_step.status = StepStatus.COMPLETED.value
                task_step.result = result

                await self._db.flush()
                results.append(f"Step {step_def.step_number}: {result}")

                logger.info(
                    "Step %d completed in %dms (tool=%s)",
                    step_def.step_number,
                    elapsed_ms,
                    step_def.tool_name,
                )

            except ToolTimeoutError:
                elapsed_ms = int((time.monotonic() - step_start) * 1000)
                tool_call.status = ToolCallStatus.TIMEOUT.value
                tool_call.latency_ms = elapsed_ms
                task_step.status = StepStatus.FAILED.value
                task_step.result = f"Timeout after {elapsed_ms}ms"

                task.status = TaskStatus.FAILED
                task.error_message = (
                    f"Step {step_def.step_number} timed out "
                    f"(tool={step_def.tool_name})"
                )
                await self._db.flush()

                logger.error(
                    "Step %d timed out (tool=%s)",
                    step_def.step_number,
                    step_def.tool_name,
                )
                raise

            except (InvalidInputError, ToolUnavailableError, ToolError) as exc:
                elapsed_ms = int((time.monotonic() - step_start) * 1000)
                tool_call.status = ToolCallStatus.FAILED.value
                tool_call.output = str(exc)
                tool_call.latency_ms = elapsed_ms

                task_step.status = StepStatus.FAILED.value
                task_step.result = str(exc)

                task.status = TaskStatus.FAILED
                task.error_message = (
                    f"Step {step_def.step_number} failed: {exc}"
                )
                await self._db.flush()

                logger.error(
                    "Step %d failed (tool=%s): %s",
                    step_def.step_number,
                    step_def.tool_name,
                    exc,
                )
                raise

            except Exception as exc:
                elapsed_ms = int((time.monotonic() - step_start) * 1000)
                tool_call.status = ToolCallStatus.FAILED.value
                tool_call.output = str(exc)
                tool_call.latency_ms = elapsed_ms

                task_step.status = StepStatus.FAILED.value
                task_step.result = str(exc)

                task.status = TaskStatus.FAILED
                task.error_message = (
                    f"Step {step_def.step_number} unexpected error: {exc}"
                )
                await self._db.flush()

                logger.exception(
                    "Step %d unexpected error (tool=%s)",
                    step_def.step_number,
                    step_def.tool_name,
                )
                raise ToolError(
                    detail=f"Unexpected error in step {step_def.step_number}: {exc}",
                    tool_name=step_def.tool_name,
                ) from exc

        return results
