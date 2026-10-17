-- migrations/versions/008_create_errors.sql
-- Structured error records for reliability tracking.

CREATE TABLE IF NOT EXISTS errors (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id         UUID        NOT NULL REFERENCES tasks (id) ON DELETE CASCADE,
    step_id         UUID        REFERENCES task_steps (id) ON DELETE SET NULL,
    error_type      error_type  NOT NULL,
    error_code      VARCHAR(50) NOT NULL,
    error_message   TEXT        NOT NULL,
    recovery_action VARCHAR(255),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
