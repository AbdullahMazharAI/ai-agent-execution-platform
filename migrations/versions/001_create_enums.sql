-- migrations/versions/001_create_enums.sql
-- Create PostgreSQL ENUM types matching Phase 2 schema.
-- Must run before any table that references these types.

-- Task lifecycle states
CREATE TYPE task_status AS ENUM (
    'PENDING',
    'PLANNING',
    'EXECUTING',
    'SYNTHESIZING',
    'VERIFYING',
    'COMPLETED',
    'FAILED',
    'CANCELLED',
    'RETRYING'
);

-- API key lifecycle states
CREATE TYPE api_key_status AS ENUM (
    'ACTIVE',
    'REVOKED',
    'EXPIRED'
);

-- Structured error categories (maps to Phase 5 retry strategy)
CREATE TYPE error_type AS ENUM (
    'TRANSIENT',
    'LLM_RATE_LIMITED',
    'TOOL_UNAVAILABLE',
    'INVALID_INPUT',
    'TIMEOUT',
    'PERMANENT'
);
