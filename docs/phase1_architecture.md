# Phase 1: System Architecture

> **Status:** Design complete. Implementation starts Week 1.

## Overview

The AI Agent Execution Platform uses an async, event-driven architecture where:

1. FastAPI receives user requests and immediately returns a task ID
2. Tasks are queued to Redis ARQ for background processing
3. An ARQ worker runs the LangGraph agent loop
4. Results are persisted to PostgreSQL
5. Clients poll REST or consume SSE for real-time updates

## Component Diagram

```
Client
  │
  ▼
FastAPI (async)                    Port 8000
  ├─ POST /api/v1/tasks   ─────► Redis ARQ Queue
  ├─ GET  /api/v1/tasks/{id} ◄── PostgreSQL
  └─ GET  /api/v1/tasks/{id}/events ◄─ Redis Pub/Sub (SSE)
                                        │
                                        ▼
                              ARQ Worker Process
                                        │
                                        ▼
                              LangGraph Agent (8 nodes)
                                        │
                              ┌─────────┴──────────┐
                              ▼                    ▼
                         Tool Registry         LLM Gateway
                         ├─ DuckDuckGo         ├─ Groq (primary)
                         ├─ FileTool           └─ Gemini (fallback)
                         └─ PythonTool
                                        │
                                        ▼
                                   PostgreSQL
                              (9 tables, see Phase 2)
```

## Technology Stack

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Web framework | FastAPI 0.109 | Async-native, OpenAPI built-in |
| Agent runtime | LangGraph 0.0.28 | Stateful graph execution |
| Task queue | Redis ARQ | Lightweight, async-first |
| Database | PostgreSQL 16 | JSONB, full-text, reliability |
| ORM | SQLAlchemy 2 (async) | Type-safe, async sessions |
| LLM primary | Groq | Fast inference, free tier |
| LLM fallback | Google Gemini | Reliability failover |

## Key Design Decisions

- **Async everywhere**: FastAPI + asyncpg + arq — no blocking I/O
- **Circuit breaker**: LLM provider failures trigger automatic fallback (Phase 5)
- **Crash recovery**: LangGraph checkpoints in PostgreSQL (`langgraph_thread_id`)
- **Observability**: Structured logs + Prometheus metrics (Phase 5)
