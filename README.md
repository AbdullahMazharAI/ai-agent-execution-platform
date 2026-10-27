# AI Agent Execution Platform

A production-grade, event-driven AI Agent Execution Platform built with FastAPI, SQLAlchemy 2.0, PostgreSQL, Redis, ARQ, Groq, and Gemini.

---

## Architecture Overview

- **Web Framework**: FastAPI (async HTTP + dependency injection)
- **Database**: PostgreSQL 16 (asyncpg driver + SQLAlchemy 2.0 ORM)
- **Background Tasks**: ARQ + Redis (async distributed task processing)
- **LLM Gateway**: Multi-provider fallback router (Groq primary, Gemini fallback on 429/5xx/timeout)
- **Agent System**:
  - `Planner`: One-shot plan generation with Pydantic JSON schema validation
  - `Executor`: Sequential plan step execution with per-step database logging (`task_steps`, `tool_calls`)
  - `ToolRegistry`: Extensible tool system (`web_search`, `file_read`, `python_exec`, `mock_tool`)
- **Monitoring**: Prometheus client metrics

---

## Week 2 — Tools, LLM Gateway, Planner, and Worker Wiring

Week 2 connects the REST API endpoints to a functioning background execution pipeline:
`POST /tasks` → save task to database → enqueue to ARQ queue → worker runs Planner → worker executes plan steps with tools → results and execution metrics saved to database.

### 1. Seed a User and API Key

Generate an initial developer user and display the raw API key (stored securely as a SHA-256 hash):

```bash
python scripts/seed_user.py
```

Output:
```text
============================================================
API KEY GENERATED SUCCESSFULLY
============================================================
Raw API Key : sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
Key Prefix  : sk-xxxx
User ID     : xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
============================================================
SAVE THIS KEY NOW. It will never be shown again.
```

### 2. Start the ARQ Background Worker

Run the ARQ worker process using the platform's worker settings:

```bash
arq app.workers.settings.WorkerSettings
```

### 3. Run the Test Suite

Execute all unit and integration tests across Week 1 and Week 2 modules:

```bash
pytest tests/ -v
```

### 4. Example API Request (POST /tasks)

Submit a task using `curl.exe` in PowerShell:

```powershell
curl.exe -X POST "http://localhost:8000/api/v1/tasks" `
  -H "Content-Type: application/json" `
  -H "X-API-Key: sk-YOUR_GENERATED_API_KEY" `
  -d '{"goal": "Search the web for latest FastAPI release notes and save summary"}'
```

Response:
```json
{
  "task_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "status": "PENDING",
  "created_at": "2026-10-20T23:00:00Z"
}
```

Check task details:

```powershell
curl.exe -X GET "http://localhost:8000/api/v1/tasks/3fa85f64-5717-4562-b3fc-2c963f66afa6" `
  -H "X-API-Key: sk-YOUR_GENERATED_API_KEY"
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in provider keys:

| Variable | Description | Default |
| --- | --- | --- |
| `DATABASE_URL` | PostgreSQL async connection URI | `postgresql+asyncpg://user:password@localhost:5432/agent_platform` |
| `REDIS_URL` | Redis connection URI | `redis://localhost:6379` |
| `GROQ_API_KEY` | Groq API key | - |
| `GROQ_MODEL` | Groq LLM model name | `llama-3.1-8b-instant` |
| `GEMINI_API_KEY` | Google Gemini API key | - |
| `GEMINI_MODEL` | Gemini LLM model name | `gemini-1.5-flash` |
| `LLM_TIMEOUT_SECONDS` | Gateway request timeout | `60` |
| `FILE_TOOL_ROOT` | Allowed root path for file reads | `./uploads` |
| `PYTHON_TOOL_TIMEOUT_SECONDS` | Subprocess Python tool timeout | `10` |
| `TOOL_TIMEOUT_SECONDS` | Default tool execution timeout | `30` |
