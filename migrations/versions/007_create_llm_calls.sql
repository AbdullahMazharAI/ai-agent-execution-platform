-- migrations/versions/007_create_llm_calls.sql
-- Audit log of every LLM inference request.

CREATE TABLE IF NOT EXISTS llm_calls (
    id                UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id           UUID         NOT NULL REFERENCES tasks (id) ON DELETE CASCADE,
    provider          VARCHAR(50)  NOT NULL,    -- GROQ | GEMINI | OLLAMA
    model_name        VARCHAR(255),
    prompt_tokens     INTEGER      NOT NULL DEFAULT 0,
    completion_tokens INTEGER      NOT NULL DEFAULT 0,
    total_tokens      INTEGER      NOT NULL DEFAULT 0,
    was_fallback      BOOLEAN      NOT NULL DEFAULT FALSE,
    finish_reason     VARCHAR(50),               -- stop | length | tool_calls
    latency_ms        INTEGER,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
