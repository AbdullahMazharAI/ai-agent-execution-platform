"""
tests/test_api.py
=================
API endpoint tests — Week 1 foundation.

These tests use HTTPX's async test client against the FastAPI app
*without* a real database or Redis.  They verify:
  - Routing and HTTP status codes
  - Auth enforcement (401 on missing/invalid key)
  - Response schema shapes
  - Basic stub responses

Week 2 will add integration tests with a real test database.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


# ── Fixtures ───────────────────────────────────────────────────────────────────
@pytest.fixture
async def client() -> AsyncClient:
    """Async HTTPX client bound to the FastAPI app (no real I/O)."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as c:
        yield c


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """Valid API key headers for authenticated requests."""
    return {"X-API-Key": "sk-test-key-week1"}


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
    task_id = "550e8400-e29b-41d4-a716-446655440000"
    response = await client.get(f"/api/v1/tasks/{task_id}", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] == task_id
    assert "status" in body
    assert "goal" in body


@pytest.mark.asyncio
async def test_list_tasks_returns_empty_list(client: AsyncClient, auth_headers: dict) -> None:
    """GET /api/v1/tasks → 200 with tasks array."""
    response = await client.get("/api/v1/tasks", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert "tasks" in body
    assert "total" in body
    assert isinstance(body["tasks"], list)


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
    task_id = "550e8400-e29b-41d4-a716-446655440000"
    response = await client.post(
        f"/api/v1/tasks/{task_id}/cancel", headers=auth_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert "status" in body


@pytest.mark.asyncio
async def test_get_task_steps(client: AsyncClient, auth_headers: dict) -> None:
    """GET /api/v1/tasks/{id}/steps → 200 with steps array."""
    task_id = "550e8400-e29b-41d4-a716-446655440000"
    response = await client.get(f"/api/v1/tasks/{task_id}/steps", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert "steps" in body


@pytest.mark.asyncio
async def test_get_task_result(client: AsyncClient, auth_headers: dict) -> None:
    """GET /api/v1/tasks/{id}/result → 200."""
    task_id = "550e8400-e29b-41d4-a716-446655440000"
    response = await client.get(f"/api/v1/tasks/{task_id}/result", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert "task_id" in body
    assert "status" in body


@pytest.mark.asyncio
async def test_get_task_errors(client: AsyncClient, auth_headers: dict) -> None:
    """GET /api/v1/tasks/{id}/errors → 200 with errors array."""
    task_id = "550e8400-e29b-41d4-a716-446655440000"
    response = await client.get(f"/api/v1/tasks/{task_id}/errors", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert "errors" in body


@pytest.mark.asyncio
async def test_retry_task(client: AsyncClient, auth_headers: dict) -> None:
    """POST /api/v1/tasks/{id}/retry → 200."""
    task_id = "550e8400-e29b-41d4-a716-446655440000"
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
