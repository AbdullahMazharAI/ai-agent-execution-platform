-- migrations/versions/009_create_verification_and_metrics.sql
-- Verification run results and aggregated usage metrics.

-- ── Verification runs ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS verification_runs (
    id                    UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id               UUID        NOT NULL REFERENCES tasks (id) ON DELETE CASCADE,
    section_completeness  BOOLEAN     NOT NULL DEFAULT FALSE,
    json_validity         BOOLEAN     NOT NULL DEFAULT FALSE,
    step_completion       BOOLEAN     NOT NULL DEFAULT FALSE,
    truncation_check      BOOLEAN     NOT NULL DEFAULT FALSE,
    hallucination_check   BOOLEAN     NOT NULL DEFAULT FALSE,
    passed                BOOLEAN     NOT NULL DEFAULT FALSE,  -- TRUE iff all checks pass
    verification_issues   JSONB,                               -- List of issue descriptions
    attempt_count         INTEGER     NOT NULL DEFAULT 1,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_verification_runs_task_id UNIQUE (task_id)
);

-- ── Usage metrics ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS usage_metrics (
    id                  UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id             UUID           NOT NULL REFERENCES tasks (id) ON DELETE CASCADE,
    total_tokens_used   INTEGER        NOT NULL DEFAULT 0,
    estimated_cost      NUMERIC(10, 6) NOT NULL DEFAULT 0.0,
    execution_time_ms   INTEGER        NOT NULL DEFAULT 0,
    tool_calls_count    INTEGER        NOT NULL DEFAULT 0,
    llm_calls_count     INTEGER        NOT NULL DEFAULT 0,
    retries_count       INTEGER        NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ    NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_usage_metrics_task_id UNIQUE (task_id)
);
