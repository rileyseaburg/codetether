-- Migration 034: DB-level guard for duplicate active GitHub App PR/issue work
--
-- Application code stores a deterministic metadata.github_work_key for each
-- GitHub App workflow stage and PR/issue commit.  This partial unique index is
-- a storage-level backstop: concurrent webhook/active-work dispatches cannot
-- create more than one active task for the same key, even across API pods.
--
-- Existing historical tasks do not have github_work_key, so this migration is
-- safe to apply before/after duplicate cleanup.
--
-- Note: project migrations run inside a transaction, so this intentionally does
-- not use CREATE INDEX CONCURRENTLY.

CREATE UNIQUE INDEX IF NOT EXISTS idx_tasks_github_app_active_work_key
ON tasks ((metadata->>'github_work_key'))
WHERE metadata->>'github_work_key' IS NOT NULL
  AND metadata->>'source' = 'github-app'
  AND status IN ('pending', 'queued', 'running', 'working');

INSERT INTO schema_migrations (migration_name, checksum)
VALUES ('034_github_app_work_dedupe_key', md5('034_github_app_work_dedupe_key'))
ON CONFLICT (migration_name) DO UPDATE SET applied_at = NOW();
