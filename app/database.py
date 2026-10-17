"""
app/database.py
===============
Async SQLAlchemy engine + session factory used by the entire application.

Usage in FastAPI endpoints (dependency injection):
    async def my_endpoint(db: AsyncSession = Depends(get_db_session)):
        ...

Usage in workers / scripts:
    async with async_session_factory() as session:
        ...
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import AsyncAdaptedQueuePool

from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# ── Engine ─────────────────────────────────────────────────────────────────────
engine = create_async_engine(
    settings.DATABASE_URL,
    poolclass=AsyncAdaptedQueuePool,
    pool_size=15,
    max_overflow=25,
    pool_timeout=30.0,
    pool_recycle=1800,       # Recycle connections every 30 min
    pool_pre_ping=True,      # Verify connection is alive before using it
    echo=settings.DATABASE_ECHO,
    future=True,
)

# ── Session factory ────────────────────────────────────────────────────────────
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Don't expire objects after commit (avoids lazy-load issues)
    autocommit=False,
    autoflush=False,
)


# ── FastAPI dependency ─────────────────────────────────────────────────────────
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an ``AsyncSession`` and guarantee cleanup on exit.

    Automatically rolls back on exception so callers never have to.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Context-manager helper (non-FastAPI code) ──────────────────────────────────
@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Context manager version for use outside FastAPI (workers, scripts, tests)."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Lifecycle helpers ──────────────────────────────────────────────────────────
async def init_db() -> None:
    """Called at application startup.

    Alembic manages schema migrations; this function is a hook for any
    runtime database initialisation (e.g. seed data in development).
    """
    logger.info("Database engine initialised (pool_size=%d)", engine.pool.size())  # type: ignore[attr-defined]


async def close_db() -> None:
    """Dispose the connection pool on application shutdown."""
    await engine.dispose()
    logger.info("Database connection pool closed.")
