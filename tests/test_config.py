"""
tests/test_config.py
====================
Unit tests for configuration in app/config.py.

Verifies:
  - Default settings loading
  - Environment validator
  - Log level validator
  - get_settings caching
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config import Settings, get_settings


class TestConfig:
    def test_default_settings(self) -> None:
        settings = Settings()
        assert settings.ENVIRONMENT == "development"
        assert settings.DEBUG is True
        assert settings.API_VERSION == "0.1.0"
        assert settings.PROMETHEUS_ENABLED is True

    def test_invalid_environment_raises(self) -> None:
        with pytest.raises(ValidationError):
            Settings(ENVIRONMENT="invalid_env")

    def test_invalid_log_level_raises(self) -> None:
        with pytest.raises(ValidationError):
            Settings(LOG_LEVEL="TRACE")

    def test_log_level_case_insensitivity(self) -> None:
        settings = Settings(LOG_LEVEL="debug")
        assert settings.LOG_LEVEL == "DEBUG"

    def test_get_settings_singleton(self) -> None:
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2
