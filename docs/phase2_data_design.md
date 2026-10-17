# Phase 2: Data Design

> **Status:** Design complete. ORM models in `app/db/models.py`. SQL migrations in `migrations/versions/`.

## Table Inventory (9 tables)

| # | Table | Description |
|---|-------|-------------|
| 1 | `users` | Platform user accounts |
| 2 | `api_keys` | Hashed API keys per user |
| 3 | `tasks` | Core task entity |
| 4 | `task_steps` | Steps within a task's execution plan |
| 5 | `tool_calls` | Every tool invocation (audit) |
| 6 | `llm_calls` | Every LLM inference request (audit) |
| 7 | `errors` | Structured error log |
| 8 | `verification_runs` | Verification node output |
| 9 | `usage_metrics` | Aggregated resource consumption |

## PostgreSQL ENUMs

```sql
task_status:    PENDING | PLANNING | EXECUTING | VERIFYING | COMPLETED | FAILED | CANCELLED | RETRYING
api_key_status: ACTIVE | REVOKED | EXPIRED
error_type:     TRANSIENT | LLM_RATE_LIMITED | TOOL_UNAVAILABLE | INVALID_INPUT | TIMEOUT | PERMANENT
```

## Entity Relationship

```
users ──< api_keys
users ──< tasks ──< task_steps ──< tool_calls
                ──< tool_calls
                ──< llm_calls
                ──< errors
                ──1 verification_runs
                ──1 usage_metrics
```

## Migration Order

Run SQL files in order:
```
000_create_extensions.sql   ← pgcrypto, pg_trgm, btree_gin
001_create_enums.sql        ← task_status, api_key_status, error_type
002_create_users.sql
003_create_api_keys.sql
004_create_tasks.sql
005_create_task_steps.sql
006_create_tool_calls.sql
007_create_llm_calls.sql
008_create_errors.sql
009_create_verification_and_metrics.sql
010_create_indexes.sql      ← All performance indexes
```
