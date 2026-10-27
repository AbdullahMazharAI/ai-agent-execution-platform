"""
app/workers/settings.py
=======================
ARQ WorkerSettings for the background worker.

Start the worker with:
    arq app.workers.settings.WorkerSettings
"""

from __future__ import annotations

from app.core.queue import REDIS_SETTINGS
from app.workers.execute_task import execute_task


class WorkerSettings:
    """ARQ worker configuration.

    Start the worker with:
        arq app.workers.settings.WorkerSettings
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

    on_startup = None
    on_shutdown = None
