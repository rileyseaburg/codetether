-- ============================================
-- PostgreSQL Row-Level Security (RLS) Rollback
-- A2A Server Multi-Tenant Isolation
-- ============================================
--
-- This script completely disables RLS and removes all policies.
-- Use this to rollback the enable_rls.sql migration.
--
-- WARNING: This will remove all tenant isolation at the database level.
-- Application-level filtering will still be active, but defense-in-depth
-- will be reduced.
--
-- Usage:
--   psql -d a2a_server -f disable_rls.sql
-- ============================================

BEGIN;

-- ============================================
-- Disable RLS on Workers Table
-- ============================================

DROP POLICY IF EXISTS tenant_isolation_workers_select ON workers;
DROP POLICY IF EXISTS tenant_isolation_workers_insert ON workers;
DROP POLICY IF EXISTS tenant_isolation_workers_update ON workers;
DROP POLICY IF EXISTS tenant_isolation_workers_delete ON workers;
DROP POLICY IF EXISTS admin_bypass_workers ON workers;

ALTER TABLE workers DISABLE ROW LEVEL SECURITY;

-- ============================================
-- Disable RLS on Codebases Table
-- ============================================

DROP POLICY IF EXISTS tenant_isolation_codebases_select ON codebases;
DROP POLICY IF EXISTS tenant_isolation_codebases_insert ON codebases;
DROP POLICY IF EXISTS tenant_isolation_codebases_update ON codebases;
DROP POLICY IF EXISTS tenant_isolation_codebases_delete ON codebases;
DROP POLICY IF EXISTS admin_bypass_codebases ON codebases;

ALTER TABLE codebases DISABLE ROW LEVEL SECURITY;

-- ============================================
-- Disable RLS on Tasks Table
-- ============================================

DROP POLICY IF EXISTS tenant_isolation_tasks_select ON tasks;
DROP POLICY IF EXISTS tenant_isolation_tasks_insert ON tasks;
DROP POLICY IF EXISTS tenant_isolation_tasks_update ON tasks;
DROP POLICY IF EXISTS tenant_isolation_tasks_delete ON tasks;
DROP POLICY IF EXISTS admin_bypass_tasks ON tasks;

ALTER TABLE tasks DISABLE ROW LEVEL SECURITY;

-- ============================================
-- Disable RLS on Sessions Table
-- ============================================

DROP POLICY IF EXISTS tenant_isolation_sessions_select ON sessions;
DROP POLICY IF EXISTS tenant_isolation_sessions_insert ON sessions;
DROP POLICY IF EXISTS tenant_isolation_sessions_update ON sessions;
DROP POLICY IF EXISTS tenant_isolation_sessions_delete ON sessions;
DROP POLICY IF EXISTS admin_bypass_sessions ON sessions;

ALTER TABLE sessions DISABLE ROW LEVEL SECURITY;

-- ============================================
-- Remove helper functions (optional - keep for potential re-enable)
-- ============================================

-- Uncomment to remove functions completely:
-- DROP FUNCTION IF EXISTS get_current_tenant_id();
-- DROP FUNCTION IF EXISTS log_rls_access(TEXT, TEXT, TEXT, JSONB);

-- ============================================
-- Update migration tracking
-- ============================================

DELETE FROM schema_migrations WHERE migration_name = 'enable_rls';

COMMIT;

-- ============================================
-- Summary output
-- ============================================

DO $$
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '============================================';
    RAISE NOTICE 'RLS Rollback Complete';
    RAISE NOTICE '============================================';
    RAISE NOTICE 'Tables with RLS disabled:';
    RAISE NOTICE '  - workers';
    RAISE NOTICE '  - codebases';
    RAISE NOTICE '  - tasks';
    RAISE NOTICE '  - sessions';
    RAISE NOTICE '';
    RAISE NOTICE 'All RLS policies have been removed.';
    RAISE NOTICE 'Application-level tenant filtering remains active.';
    RAISE NOTICE '';
    RAISE NOTICE 'To re-enable RLS:';
    RAISE NOTICE '  Run enable_rls.sql';
    RAISE NOTICE '============================================';
END $$;
