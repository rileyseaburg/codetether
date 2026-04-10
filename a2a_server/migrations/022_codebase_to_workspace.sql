-- Migration: Rename "codebase" to "workspace" throughout the schema.
-- This is a non-destructive migration that preserves all data via ALTER RENAME.
-- A backward-compat VIEW is created so old queries against "codebases" still work.

BEGIN;

-- ============================================================
-- 1. Rename the primary table
-- ============================================================
ALTER TABLE IF EXISTS codebases RENAME TO workspaces;

-- ============================================================
-- 2. Rename foreign-key columns in dependent tables
-- ============================================================
ALTER TABLE tasks          RENAME COLUMN codebase_id TO workspace_id;
ALTER TABLE sessions       RENAME COLUMN codebase_id TO workspace_id;
ALTER TABLE ralph_runs     RENAME COLUMN codebase_id TO workspace_id;
ALTER TABLE perpetual_loops RENAME COLUMN codebase_id TO workspace_id;
ALTER TABLE prd_chat_sessions RENAME COLUMN codebase_id TO workspace_id;
ALTER TABLE inbound_emails  RENAME COLUMN codebase_id TO workspace_id;
ALTER TABLE outbound_emails RENAME COLUMN codebase_id TO workspace_id;
ALTER TABLE workers        RENAME COLUMN global_codebase_id TO global_workspace_id;

-- ============================================================
-- 3. Rename indexes on the workspaces (formerly codebases) table
-- ============================================================
ALTER INDEX IF EXISTS idx_codebases_worker  RENAME TO idx_workspaces_worker;
ALTER INDEX IF EXISTS idx_codebases_status  RENAME TO idx_workspaces_status;
ALTER INDEX IF EXISTS idx_codebases_path    RENAME TO idx_workspaces_path;
ALTER INDEX IF EXISTS idx_codebases_tenant  RENAME TO idx_workspaces_tenant;

-- ============================================================
-- 4. Rename indexes on dependent tables
-- ============================================================
ALTER INDEX IF EXISTS idx_tasks_codebase    RENAME TO idx_tasks_workspace;
ALTER INDEX IF EXISTS idx_sessions_codebase RENAME TO idx_sessions_workspace;
ALTER INDEX IF EXISTS idx_ralph_runs_codebase RENAME TO idx_ralph_runs_workspace;
ALTER INDEX IF EXISTS idx_prd_chat_sessions_codebase RENAME TO idx_prd_chat_sessions_workspace;

-- ============================================================
-- 5. Rename unique constraint on prd_chat_sessions
--    (constraint name is auto-generated; rename if it exists)
-- ============================================================
DO $$
BEGIN
    -- Try to rename the unique constraint that includes codebase_id
    -- PostgreSQL may have auto-named it; we handle both cases
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'prd_chat_sessions'::regclass
        AND conname LIKE '%codebase%'
    ) THEN
        EXECUTE format(
            'ALTER TABLE prd_chat_sessions RENAME CONSTRAINT %I TO %I',
            (SELECT conname FROM pg_constraint
             WHERE conrelid = 'prd_chat_sessions'::regclass
             AND conname LIKE '%codebase%' LIMIT 1),
            replace(
                (SELECT conname FROM pg_constraint
                 WHERE conrelid = 'prd_chat_sessions'::regclass
                 AND conname LIKE '%codebase%' LIMIT 1),
                'codebase', 'workspace')
        );
    END IF;
END $$;

-- ============================================================
-- 6. Rename RLS policies (if RLS is enabled)
-- ============================================================
DO $$
BEGIN
    -- Rename tenant isolation policies
    IF EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'workspaces' AND policyname = 'tenant_isolation_codebases_select') THEN
        ALTER POLICY tenant_isolation_codebases_select ON workspaces RENAME TO tenant_isolation_workspaces_select;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'workspaces' AND policyname = 'tenant_isolation_codebases_insert') THEN
        ALTER POLICY tenant_isolation_codebases_insert ON workspaces RENAME TO tenant_isolation_workspaces_insert;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'workspaces' AND policyname = 'tenant_isolation_codebases_update') THEN
        ALTER POLICY tenant_isolation_codebases_update ON workspaces RENAME TO tenant_isolation_workspaces_update;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'workspaces' AND policyname = 'tenant_isolation_codebases_delete') THEN
        ALTER POLICY tenant_isolation_codebases_delete ON workspaces RENAME TO tenant_isolation_workspaces_delete;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'workspaces' AND policyname = 'admin_bypass_codebases') THEN
        ALTER POLICY admin_bypass_codebases ON workspaces RENAME TO admin_bypass_workspaces;
    END IF;
END $$;

-- ============================================================
-- 7. Create backward-compat VIEW for transition period
-- ============================================================
CREATE OR REPLACE VIEW codebases AS SELECT * FROM workspaces;

COMMIT;
