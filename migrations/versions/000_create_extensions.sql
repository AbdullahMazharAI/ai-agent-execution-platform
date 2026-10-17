-- migrations/versions/000_create_extensions.sql
-- Run ONCE on a fresh database to enable required PostgreSQL extensions.
-- Executed automatically by Docker Compose via docker-entrypoint-initdb.d/

-- pgcrypto: gen_random_uuid() for UUID primary keys
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- pg_trgm: trigram indexes for fast LIKE / ILIKE search on text columns (future use)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- btree_gin: composite GIN indexes combining btree-sortable columns (future use)
CREATE EXTENSION IF NOT EXISTS btree_gin;
