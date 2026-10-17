"""
app/main.py
===========
FastAPI application entry point.

Startup order:
  1. Logging configured
  2. Database engine initialised
  3. ARQ Redis queue initialised
  4. Routers mounted
  5. Prometheus (if enabled) registered

Shutdown order (reverse):
  1. Database pool disposed
"""

from __future__ import annotations

import logging
import logging.config
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database import init_db, close_db
from app.core.errors import AppError
from app.api.v1 import endpoints

settings = get_settings()

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Lifespan ───────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    """Manage application startup and graceful shutdown."""
    # ── Startup ──────────────────────────────────────────────
    logger.info("🚀 Starting AI Agent Execution Platform (%s)", settings.ENVIRONMENT)

    await init_db()
    logger.info("✅ Database pool ready")

    # ARQ queue is initialised lazily per-request (avoid blocking startup if
    # Redis is not yet available in development).  Full initialisation happens
    # in core/queue.py when the first task is enqueued.
    logger.info("✅ Application startup complete")

    yield  # ← server is running

    # ── Shutdown ─────────────────────────────────────────────
    logger.info("🛑 Shutting down...")
    await close_db()
    logger.info("👋 Shutdown complete")


# ── App factory ────────────────────────────────────────────────────────────────
def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.API_TITLE,
        version=settings.API_VERSION,
        description=(
            "A production-grade AI agent that plans and executes multi-step "
            "tasks using LLMs and tools."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # ── Middleware ────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.DEBUG else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Exception handlers ────────────────────────────────────────────────
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.error_code, "detail": exc.detail},
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception for %s %s", request.method, request.url)
        return JSONResponse(
            status_code=500,
            content={"error": "INTERNAL_SERVER_ERROR", "detail": "An unexpected error occurred."},
        )

    # ── Routes ────────────────────────────────────────────────────────────
    app.include_router(endpoints.router, prefix="/api/v1")

    # ── Health check ──────────────────────────────────────────────────────
    @app.get("/health", tags=["meta"], summary="Health check")
    async def health_check() -> dict[str, Any]:
        """Returns service liveness status (Phase 3)."""
        from datetime import datetime, timezone
        return {
            "status": "healthy",
            "environment": settings.ENVIRONMENT,
            "version": settings.API_VERSION,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    return app


app = create_app()


# ── Dev runner ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
