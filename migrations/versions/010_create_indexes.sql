-- migrations/versions/010_create_indexes.sql
-- Performance indexes for the most common query patterns.
-- Run AFTER all tables are created (migrations 002–009).

-- ── tasks ─────────────────────────────────────────────────────────────────────
-- Dashboard: list tasks for a user filtered/sorted by status + date
CREATE INDEX IF NOT EXISTS idx_tasks_user_status
    ON tasks (user_id, status);

CREATE INDEX IF NOT EXISTS idx_tasks_created_at
    ON tasks (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_tasks_status
    ON tasks (status);

-- ── task_steps ────────────────────────────────────────────────────────────────
-- Fetch ordered steps for a given task
CREATE INDEX IF NOT EXISTS idx_task_steps_task_id
    ON task_steps (task_id, step_number);

-- ── tool_calls ────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_tool_calls_task_id
    ON tool_calls (task_id);

CREATE INDEX IF NOT EXISTS idx_tool_calls_step_id
    ON tool_calls (step_id);

-- ── llm_calls ─────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_llm_calls_task_id
    ON llm_calls (task_id);

-- Analytics: aggregate token usage per provider
CREATE INDEX IF NOT EXISTS idx_llm_calls_provider
    ON llm_calls (provider);

-- ── errors ────────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_errors_task_id
    ON errors (task_id);

CREATE INDEX IF NOT EXISTS idx_errors_error_type
    ON errors (error_type);

-- ── verification_runs ─────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_verification_runs_task_id
    ON verification_runs (task_id);

-- ── usage_metrics ─────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_usage_metrics_task_id
    ON usage_metrics (task_id);
