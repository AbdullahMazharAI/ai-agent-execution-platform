"""
tests/test_queue.py
===================
Unit tests for ARQ Redis queue configuration in app/core/queue.py.

Verifies:
  - Redis URL parsing logic for various URL formats
  - WorkerSettings configuration parameters
"""

from __future__ import annotations

import pytest
from app.core.queue import WorkerSettings, _parse_redis_settings
from app.config import Settings


class TestQueueConfig:
    def test_worker_settings(self) -> None:
        assert WorkerSettings.max_jobs == 10
        assert WorkerSettings.keep_result == 86_400
        assert WorkerSettings.job_timeout == 1_800
        assert WorkerSettings.max_tries == 3
        assert len(WorkerSettings.functions) == 1

    def test_parse_redis_settings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Test standard host:port
        monkeypatch.setattr("app.core.queue.settings.REDIS_URL", "redis://redis-host:6380")
        settings_obj = _parse_redis_settings()
        assert settings_obj.host == "redis-host"
        assert settings_obj.port == 6380
        assert settings_obj.database == 0

        # Test with database index
        monkeypatch.setattr("app.core.queue.settings.REDIS_URL", "redis://localhost:6379/3")
        settings_obj = _parse_redis_settings()
        assert settings_obj.host == "localhost"
        assert settings_obj.port == 6379
        assert settings_obj.database == 3
