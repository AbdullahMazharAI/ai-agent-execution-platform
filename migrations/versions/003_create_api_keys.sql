-- migrations/versions/003_create_api_keys.sql
-- Hashed API keys linked to users.

CREATE TABLE IF NOT EXISTS api_keys (
    id           UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID           NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    key_hash     VARCHAR(64)    NOT NULL,          -- SHA-256 hex digest of the raw key
    key_prefix   VARCHAR(8)     NOT NULL,          -- First 8 chars displayed in UI (e.g. "sk-ab12")
    status       api_key_status NOT NULL DEFAULT 'ACTIVE',
    expires_at   TIMESTAMPTZ,                      -- NULL = never expires
    created_at   TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    last_used_at TIMESTAMPTZ,

    CONSTRAINT uq_api_keys_key_hash UNIQUE (key_hash)
);

-- Partial index: only index ACTIVE keys for O(1) authentication lookups
CREATE UNIQUE INDEX IF NOT EXISTS idx_api_keys_active_lookup
    ON api_keys (key_hash)
    WHERE status = 'ACTIVE';

-- List all keys for a given user (admin / dashboard)
CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON api_keys (user_id);
