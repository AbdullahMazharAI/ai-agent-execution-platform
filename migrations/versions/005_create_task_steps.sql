-- migrations/versions/005_create_task_steps.sql
-- Individual steps within a task's execution plan.

CREATE TABLE IF NOT EXISTS task_steps (
    id               UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id          UUID         NOT NULL REFERENCES tasks (id) ON DELETE CASCADE,
    step_number      INTEGER      NOT NULL,
    step_description TEXT         NOT NULL,
    tool_name        VARCHAR(255),                  -- Which tool this step uses (nullable)
    status           VARCHAR(50)  NOT NULL DEFAULT 'PENDING',
    result           TEXT,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_task_steps_task_step_num UNIQUE (task_id, step_number)
);

-- Auto-update updated_at
CREATE TRIGGER trg_task_steps_updated_at
    BEFORE UPDATE ON task_steps
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
