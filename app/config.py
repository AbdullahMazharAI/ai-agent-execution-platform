"""
app/config.py
=============
Application configuration loaded from environment variables / .env file.

All settings are validated by Pydantic on startup, so a missing required
variable will raise a clear error before the server accepts any traffic.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── API ────────────────────────────────────────────────────────────────
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_TITLE: str = "AI Agent Execution Platform"
    API_VERSION: str = "0.1.0"
    SECRET_KEY: str = "change-me-in-production"

    # ── Database ───────────────────────────────────────────────────────────
    DATABASE_URL: str = (
        "postgresql+asyncpg://user:password@localhost:5432/agent_platform"
    )
    DATABASE_ECHO: bool = False

    # ── Redis ──────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379"

    # ── LLM Providers ─────────────────────────────────────────────────────
    GROQ_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # ── Monitoring ─────────────────────────────────────────────────────────
    PROMETHEUS_ENABLED: bool = True
    LOG_LEVEL: str = "INFO"

    @field_validator("ENVIRONMENT")
    @classmethod
    def environment_must_be_valid(cls, v: str) -> str:
        allowed = {"development", "staging", "production"}
        if v not in allowed:
            raise ValueError(f"ENVIRONMENT must be one of {allowed}; got {v!r}")
        return v

    @field_validator("LOG_LEVEL")
    @classmethod
    def log_level_must_be_valid(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of {allowed}; got {v!r}")
        return upper

    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "ignore",
    }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance (singleton).

    Using ``lru_cache`` instead of a module-level global ensures that the
    settings are constructed only once and that the cache can be cleared in
    tests with ``get_settings.cache_clear()``.
    """
    return Settings()
