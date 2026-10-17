"""
app/core/queue.py
=================
ARQ Redis queue setup and task enqueueing utilities.

ARQ documentation: https://arq-docs.helpmanual.io/

The ``WorkerSettings`` class is imported by the ARQ CLI to start the worker:
    arq app.core.queue.WorkerSettings

Week 2: The ``execute_task`` function body will be implemented in
         ``app/workers/execute_task.py``.
"""

from __future__ import annotations

import logging
from typing import Any

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# ── Redis connection settings for ARQ ─────────────────────────────────────────
def _parse_redis_settings() -> RedisSettings:
    """Parse ``REDIS_URL`` into an ARQ ``RedisSettings`` object.

    Handles both ``redis://host:port`` and ``redis://host:port/db`` forms.
    """
    url = settings.REDIS_URL  # e.g. "redis://localhost:6379" or "redis://localhost:6379/0"
    # Strip scheme
    without_scheme = url.split("://", 1)[-1]
    # Split host:port/db
    if "/" in without_scheme:
        host_port, db_str = without_scheme.rsplit("/", 1)
        database = int(db_str) if db_str.isdigit() else 0
    else:
        host_port = without_scheme
        database = 0

    if ":" in host_port:
        host, port_str = host_port.rsplit(":", 1)
        port = int(port_str)
    else:
        host = host_port
        port = 6379

    return RedisSettings(host=host, port=port, database=database)


REDIS_SETTINGS = _parse_redis_settings()


# ── Queue pool ────────────────────────────────────────────────────────────────
_queue: ArqRedis | None = None


async def get_queue() -> ArqRedis:
    """Return a cached ARQ connection pool (lazy initialisation).

    The pool is created on first call and reused for the lifetime of the
    process.  Lazy init avoids blocking application startup if Redis is not
    immediately available.
    """
    global _queue
    if _queue is None:
        logger.info(
            "Connecting to Redis ARQ queue at %s:%d db=%d",
            REDIS_SETTINGS.host,
            REDIS_SETTINGS.port,
            REDIS_SETTINGS.database,
        )
        _queue = await create_pool(REDIS_SETTINGS)
        logger.info("ARQ queue pool ready")
    return _queue


async def close_queue() -> None:
    """Close the ARQ connection pool on application shutdown."""
    global _queue
    if _queue is not None:
        await _queue.aclose()
        _queue = None
        logger.info("ARQ queue pool closed")


# ── Enqueueing helpers ─────────────────────────────────────────────────────────
async def enqueue_task(task_id: str) -> str:
    """Enqueue an ``execute_task`` job and return the ARQ job ID.

    Args:
        task_id: UUID string of the task row in PostgreSQL.

    Returns:
        The ARQ job ID (useful for later status queries).
    """
    queue = await get_queue()
    job = await queue.enqueue_job("execute_task", task_id)
    if job is None:
        # Duplicate job — ARQ de-duplicates by default
        logger.warning("enqueue_task: job already queued for task_id=%s", task_id)
        return ""
    logger.info("Enqueued execute_task | task_id=%s arq_job_id=%s", task_id, job.job_id)
    return job.job_id


async def enqueue_task_with_delay(task_id: str, delay_seconds: float) -> str:
    """Enqueue an ``execute_task`` job with a fixed delay (useful for retries).

    Args:
        task_id:       UUID string of the task.
        delay_seconds: Number of seconds to wait before the job is picked up.

    Returns:
        The ARQ job ID.
    """
    from datetime import datetime, timedelta, timezone

    queue = await get_queue()
    defer_until = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
    job = await queue.enqueue_job("execute_task", task_id, _defer_until=defer_until)
    if job is None:
        logger.warning(
            "enqueue_task_with_delay: job already queued for task_id=%s", task_id
        )
        return ""
    logger.info(
        "Enqueued execute_task (delayed %.1fs) | task_id=%s arq_job_id=%s",
        delay_seconds,
        task_id,
        job.job_id,
    )
    return job.job_id


# ── ARQ WorkerSettings ─────────────────────────────────────────────────────────
# Import the task function so ARQ can find it by name.
# Week 2: the real implementation lives in app/workers/execute_task.py
from app.workers.execute_task import execute_task  # noqa: E402


class WorkerSettings:
    """ARQ worker configuration.

    Start the worker with:
        arq app.core.queue.WorkerSettings

    Or in a script:
        from arq import run_worker
        run_worker(WorkerSettings)
    """

    redis_settings = REDIS_SETTINGS
    functions = [execute_task]

    # Concurrency: run up to 10 tasks in parallel
    max_jobs = 10

    # Keep completed job results for 24 hours
    keep_result = 86_400

    # Allow up to 30 minutes per task before timeout
    job_timeout = 1_800

    # Retry failed jobs up to 3 times with exponential backoff
    max_tries = 3

    on_startup = None   # Week 2: wire in DB / queue warmup
    on_shutdown = None  # Week 2: wire in graceful teardown
