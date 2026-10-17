# Phase 5: Reliability Design

> **Status:** Design complete. Exception hierarchy in `app/core/errors.py`. Full implementation Week 4.

## Retry Strategy

| Error Type | Max Retries | Backoff | Action |
|-----------|-------------|---------|--------|
| `TRANSIENT` | 3 | Exponential (1s, 2s, 4s) | Retry |
| `LLM_RATE_LIMITED` | 5 | Provider `retry-after` header | Wait + retry |
| `TOOL_UNAVAILABLE` | 2 | Fixed 5s | Retry or fallback tool |
| `INVALID_INPUT` | 0 | — | Fail immediately |
| `TIMEOUT` | 3 | Exponential | Retry with longer timeout |
| `PERMANENT` | 0 | — | Fail immediately |

## Circuit Breaker (LLM Gateway)

```
CLOSED ─(5 failures in 60s)──► OPEN
  ▲                               │
  └──(success)── HALF_OPEN ◄──(30s timeout)
```

- **CLOSED**: Normal operation, requests go through
- **OPEN**: Fast-fail, immediately fallback to next provider
- **HALF_OPEN**: One trial request; if successful, close the breaker

## Watchdog

- Polls for tasks stuck in `EXECUTING` for > 30 minutes
- Marks them `FAILED` with `error_type=TIMEOUT`
- Runs every 5 minutes via a separate ARQ cron job

## Cancellation Protocol

1. Client: `POST /api/v1/tasks/{id}/cancel`
2. API: Set Redis key `cancel:{task_id}` = "1" (TTL 3600s)
3. Agent: `CheckCancellation` node polls this key between every node
4. Agent: On detection, persist status=CANCELLED and exit gracefully

## Error Exception Hierarchy

```
AppError (base → HTTP response)
├─ NotFoundError          → 404
├─ UnauthorizedError      → 401
├─ ForbiddenError         → 403
├─ ConflictError          → 409
├─ RateLimitError         → 429
└─ InternalError          → 500
    ├─ DatabaseError
    ├─ QueueError
    └─ AgentError
           ├─ LLMError
           │   ├─ LLMRateLimitError
           │   └─ LLMTimeoutError
           ├─ ToolError
           │   ├─ ToolUnavailableError
           │   └─ ToolTimeoutError
           └─ VerificationError
```
