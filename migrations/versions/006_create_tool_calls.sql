-- migrations/versions/006_create_tool_calls.sql
-- Audit log of every tool invocation.

CREATE TABLE IF NOT EXISTS tool_calls (
    id          UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id     UUID         NOT NULL REFERENCES tasks (id) ON DELETE CASCADE,
    step_id     UUID         REFERENCES task_steps (id) ON DELETE SET NULL,
    tool_name   VARCHAR(255) NOT NULL,
    input_args  JSONB        NOT NULL DEFAULT '{}',
    output      TEXT,
    status      VARCHAR(50)  NOT NULL DEFAULT 'PENDING',  -- PENDING|SUCCESS|FAILED|TIMEOUT
    latency_ms  INTEGER,
    retry_count INTEGER      NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
