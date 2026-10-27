"""
tests/test_api.py
=================
API endpoint tests — Week 1 + Week 2 verified.

Uses an in-memory SQLite database and dependency overrides for:
  - Database session (get_db_session)
  - Queue worker enqueueing (enqueue_task)
No live Postgres or Redis required.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import get_db_session
from app.db.models import (
    APIKey,
    APIKeyStatus,
    Base,
    Error,
    ErrorType,
    StepStatus,
    Task,
    TaskStatus,
    TaskStep,
    User,
)
from app.main import app

# Fixed IDs for deterministic assertions
TEST_USER_ID = UUID("00000000-0000-0000-0000-000000000001")
TEST_TASK_ID = UUID("550e8400-e29b-41d4-a716-446655440000")
TEST_API_KEY = "sk-test-key-week1"


@pytest.fixture
async def test_db_session_factory():
    """Create in-memory SQLite engine and seed user, api_key, task, step, error."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        user = User(
            id=TEST_USER_ID,
            username="testuser",
            email="test@example.com",
            is_active=True,
        )
        session.add(user)

        key_hash = hashlib.sha256(TEST_API_KEY.encode()).hexdigest()
        api_key = APIKey(
            user_id=TEST_USER_ID,
            key_hash=key_hash,
            key_prefix=TEST_API_KEY[:7],
            status=APIKeyStatus.ACTIVE,
        )
        session.add(api_key)

        task = Task(
            id=TEST_TASK_ID,
            user_id=TEST_USER_ID,
            goal="Compare Python vs JavaScript for AI",
            status=TaskStatus.PENDING,
        )
        session.add(task)

        step = TaskStep(
            task_id=TEST_TASK_ID,
            step_number=1,
            step_description="First step",
            tool_name="mock_tool",
            status=StepStatus.COMPLETED.value,
            result="Step done",
        )
        session.add(step)

        err = Error(
            task_id=TEST_TASK_ID,
            error_type=ErrorType.TRANSIENT,
            error_code="ERR_TRANSIENT",
            error_message="Sample transient warning",
        )
        session.add(err)
        await session.commit()

    yield session_factory
    await engine.dispose()


@pytest.fixture
async def client(test_db_session_factory) -> AsyncClient:
    """Async HTTPX client with dependency overrides for DB and ARQ queue."""
    async def override_get_db_session():
        async with test_db_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db_session] = override_get_db_session

    with patch("app.api.v1.endpoints.enqueue_task", new_callable=AsyncMock):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as c:
            yield c

    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """Valid API key headers for authenticated requests."""
    return {"X-API-Key": TEST_API_KEY}


# ══════════════════════════════════════════════════════════════════════════════
# Health check
# ══════════════════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_health_check(client: AsyncClient) -> None:
    """GET /health returns 200 with status=healthy."""
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert "timestamp" in body
    assert "version" in body


# ══════════════════════════════════════════════════════════════════════════════
# Authentication
# ══════════════════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_missing_api_key_returns_401(client: AsyncClient) -> None:
    """POST /api/v1/tasks without X-API-Key → 401."""
    response = await client.post("/api/v1/tasks", json={"goal": "test"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_invalid_api_key_format_returns_401(client: AsyncClient) -> None:
    """POST /api/v1/tasks with key not starting with 'sk-' → 401."""
    response = await client.post(
        "/api/v1/tasks",
        json={"goal": "test"},
        headers={"X-API-Key": "bad-key"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_valid_api_key_prefix_accepted(client: AsyncClient, auth_headers: dict) -> None:
    """POST /api/v1/tasks with valid 'sk-' prefix key → 201 (not 401)."""
    response = await client.post(
        "/api/v1/tasks",
        json={"goal": "Test task"},
        headers=auth_headers,
    )
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_unknown_api_key_returns_401(client: AsyncClient) -> None:
    """Valid sk- prefix but non-existent key → 401."""
    response = await client.post(
        "/api/v1/tasks",
        json={"goal": "Test task"},
        headers={"X-API-Key": "sk-unknown-key-12345"},
    )
    assert response.status_code == 401


# ══════════════════════════════════════════════════════════════════════════════
# Task endpoints
# ══════════════════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_create_task_returns_task_id(client: AsyncClient, auth_headers: dict) -> None:
    """POST /api/v1/tasks → 201 with task_id in body."""
    response = await client.post(
        "/api/v1/tasks",
        json={"goal": "Compare Python vs JavaScript for AI"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert "task_id" in body
    assert "status" in body
    assert "created_at" in body
    assert body["status"] == "PENDING"


@pytest.mark.asyncio
async def test_create_task_empty_goal_returns_422(client: AsyncClient, auth_headers: dict) -> None:
    """POST /api/v1/tasks with empty goal → 422 (Pydantic validation)."""
    response = await client.post(
        "/api/v1/tasks",
        json={"goal": ""},
        headers=auth_headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_task_returns_detail(client: AsyncClient, auth_headers: dict) -> None:
    """GET /api/v1/tasks/{id} → 200 with task detail shape."""
    task_id = str(TEST_TASK_ID)
    response = await client.get(f"/api/v1/tasks/{task_id}", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] == task_id
    assert "status" in body
    assert "goal" in body


@pytest.mark.asyncio
async def test_get_nonexistent_task_returns_404(client: AsyncClient, auth_headers: dict) -> None:
    """GET /api/v1/tasks/{id} for missing task → 404."""
    missing_id = "00000000-0000-0000-0000-999999999999"
    response = await client.get(f"/api/v1/tasks/{missing_id}", headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_tasks_returns_list(client: AsyncClient, auth_headers: dict) -> None:
    """GET /api/v1/tasks → 200 with tasks array."""
    response = await client.get("/api/v1/tasks", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert "tasks" in body
    assert "total" in body
    assert isinstance(body["tasks"], list)
    assert body["total"] >= 1


@pytest.mark.asyncio
async def test_list_tasks_pagination_params(client: AsyncClient, auth_headers: dict) -> None:
    """GET /api/v1/tasks?limit=5&offset=10 → 200 with correct params echoed."""
    response = await client.get(
        "/api/v1/tasks?limit=5&offset=10", headers=auth_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 5
    assert body["offset"] == 10


@pytest.mark.asyncio
async def test_cancel_task(client: AsyncClient, auth_headers: dict) -> None:
    """POST /api/v1/tasks/{id}/cancel → 200 with status."""
    task_id = str(TEST_TASK_ID)
    response = await client.post(
        f"/api/v1/tasks/{task_id}/cancel", headers=auth_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert "status" in body


@pytest.mark.asyncio
async def test_get_task_steps(client: AsyncClient, auth_headers: dict) -> None:
    """GET /api/v1/tasks/{id}/steps → 200 with steps array."""
    task_id = str(TEST_TASK_ID)
    response = await client.get(f"/api/v1/tasks/{task_id}/steps", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert "steps" in body
    assert len(body["steps"]) >= 1


@pytest.mark.asyncio
async def test_get_task_result(client: AsyncClient, auth_headers: dict) -> None:
    """GET /api/v1/tasks/{id}/result → 200."""
    task_id = str(TEST_TASK_ID)
    response = await client.get(f"/api/v1/tasks/{task_id}/result", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert "task_id" in body
    assert "status" in body


@pytest.mark.asyncio
async def test_get_task_errors(client: AsyncClient, auth_headers: dict) -> None:
    """GET /api/v1/tasks/{id}/errors → 200 with errors array."""
    task_id = str(TEST_TASK_ID)
    response = await client.get(f"/api/v1/tasks/{task_id}/errors", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert "errors" in body
    assert len(body["errors"]) >= 1


@pytest.mark.asyncio
async def test_retry_task(client: AsyncClient, auth_headers: dict) -> None:
    """POST /api/v1/tasks/{id}/retry → 200."""
    task_id = str(TEST_TASK_ID)
    response = await client.post(
        f"/api/v1/tasks/{task_id}/retry", headers=auth_headers
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_prometheus_metrics_endpoint(client: AsyncClient) -> None:
    """GET /api/v1/metrics → 200 with text/plain content."""
    response = await client.get("/api/v1/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_invalid_uuid_returns_422(client: AsyncClient, auth_headers: dict) -> None:
    """GET /api/v1/tasks/not-a-uuid → 422 (UUID path param validation)."""
    response = await client.get("/api/v1/tasks/not-a-uuid", headers=auth_headers)
    assert response.status_code == 422
