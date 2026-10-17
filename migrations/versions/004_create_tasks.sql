-- migrations/versions/004_create_tasks.sql
-- Core task entity.

CREATE TABLE IF NOT EXISTS tasks (
    id                      UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID         NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    goal                    TEXT         NOT NULL,
    status                  task_status  NOT NULL DEFAULT 'PENDING',

    -- LangGraph / agent state
    plan                    JSONB,                      -- Generated execution plan
    result                  TEXT,                       -- Final answer / output
    error_message           TEXT,
    langgraph_thread_id     VARCHAR(255),               -- Checkpoint key for crash recovery

    -- Timing
    execution_started_at    TIMESTAMPTZ,
    execution_completed_at  TIMESTAMPTZ,
    cancelled_at            TIMESTAMPTZ,
    created_at              TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- Auto-update updated_at
CREATE TRIGGER trg_tasks_updated_at
    BEFORE UPDATE ON tasks
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
