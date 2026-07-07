-- Runs once on first postgres container start.
-- Schema itself is managed by Alembic; here we only enable extensions.
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
