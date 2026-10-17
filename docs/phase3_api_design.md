# Phase 3: API Design

> **Status:** Design complete. Stub implementations in `app/api/v1/endpoints.py`.

## Endpoints (10 total)

| # | Method | Path | Description | Week |
|---|--------|------|-------------|------|
| 1 | POST | `/api/v1/tasks` | Submit task | 2 |
| 2 | GET | `/api/v1/tasks/{id}` | Get task details | 2 |
| 3 | GET | `/api/v1/tasks` | List tasks (paginated) | 2 |
| 4 | POST | `/api/v1/tasks/{id}/cancel` | Cancel running task | 4 |
| 5 | GET | `/api/v1/tasks/{id}/events` | SSE real-time stream | 4 |
| 6 | GET | `/api/v1/tasks/{id}/steps` | Execution steps | 3 |
| 7 | GET | `/api/v1/tasks/{id}/result` | Result + verification + metrics | 4 |
| 8 | GET | `/api/v1/tasks/{id}/errors` | Error log | 3 |
| 9 | POST | `/api/v1/tasks/{id}/retry` | Retry failed task | 4 |
| 10 | GET | `/api/v1/metrics` | Prometheus scrape | 5 |

## Authentication

Every endpoint (except `/health` and `/metrics`) requires:
```
X-API-Key: sk-<your-key>
```

Keys are SHA-256 hashed and stored in the `api_keys` table.

## Rate Limiting

- 100 requests/minute per API key (Week 3)
- Redis sliding window counter

## Pagination

List endpoints support:
- `?limit=10` (1–100)
- `?offset=0`

## Error Format

```json
{
  "error": "NOT_FOUND",
  "detail": "Task '550e...' not found."
}
```
