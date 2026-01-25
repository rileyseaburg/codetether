-- ============================================
-- PostgreSQL Row-Level Security (RLS) Migration
-- A2A Server Multi-Tenant Isolation
-- ============================================
-- 
-- This migration enables Row-Level Security (RLS) on all tenant-scoped tables
-- to provide defense-in-depth database-level isolation for multi-tenant deployments.
--
-- Security Model:
-- - Uses session variable 'app.current_tenant_id' for tenant context
-- - Policies allow access only to rows matching the current tenant
-- - NULL tenant context allows access for backward compatibility (opt-in RLS)
-- - Admin role bypasses RLS for maintenance operations
--
-- Usage:
-- 1. Run this migration with: psql -d a2a_server -f enable_rls.sql
-- 2. Set tenant context before queries: SET app.current_tenant_id = 'tenant-uuid';
-- 3. Clear context after: RESET app.current_tenant_id;
--
-- Rollback:
-- Run disable_rls.sql to completely disable RLS and remove all policies.
-- ============================================

-- Start transaction for atomic application
BEGIN;

-- ============================================
-- Create admin role for bypassing RLS
-- ============================================

-- Create the admin role if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'a2a_admin') THEN
        CREATE ROLE a2a_admin NOLOGIN;
        RAISE NOTICE 'Created role: a2a_admin';
    END IF;
END $$;

-- Create the application role if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'a2a_app') THEN
        CREATE ROLE a2a_app NOLOGIN;
        RAISE NOTICE 'Created role: a2a_app';
    END IF;
END $$;

-- ============================================
-- Helper function to get current tenant ID
-- ============================================

CREATE OR REPLACE FUNCTION get_current_tenant_id()
RETURNS TEXT AS $$
DECLARE
    tenant_id TEXT;
BEGIN
    -- Get the session variable
    -- IMPORTANT: current_setting returns '' (empty string) not NULL when not set
    tenant_id := current_setting('app.current_tenant_id', true);
    
    -- Treat both NULL and empty string as "no tenant context"
    IF tenant_id IS NULL OR tenant_id = '' THEN
        RETURN NULL;
    END IF;
    
    RETURN tenant_id;
EXCEPTION
    WHEN OTHERS THEN
        RETURN NULL;
END;
$$ LANGUAGE plpgsql STABLE SECURITY DEFINER;

COMMENT ON FUNCTION get_current_tenant_id() IS 
'Returns the current tenant ID from session variable, or NULL if not set.
Used by RLS policies for tenant isolation.
NOTE: current_setting() returns empty string when not set, so we convert that to NULL.';

-- ============================================
-- RLS Audit logging function
-- ============================================

CREATE TABLE IF NOT EXISTS rls_audit_log (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    table_name TEXT NOT NULL,
    operation TEXT NOT NULL,
    tenant_id TEXT,
    row_tenant_id TEXT,
    user_name TEXT DEFAULT CURRENT_USER,
    session_user_name TEXT DEFAULT SESSION_USER,
    details JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_rls_audit_timestamp ON rls_audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_rls_audit_tenant ON rls_audit_log(tenant_id);
CREATE INDEX IF NOT EXISTS idx_rls_audit_table ON rls_audit_log(table_name);

COMMENT ON TABLE rls_audit_log IS 
'Audit log for RLS policy violations and access attempts.
Records when tenant context mismatches occur for security monitoring.';

-- Function to log RLS violations (called when policies block access)
CREATE OR REPLACE FUNCTION log_rls_access(
    p_table_name TEXT,
    p_operation TEXT,
    p_row_tenant_id TEXT,
    p_details JSONB DEFAULT '{}'::jsonb
)
RETURNS VOID AS $$
BEGIN
    INSERT INTO rls_audit_log (table_name, operation, tenant_id, row_tenant_id, details)
    VALUES (p_table_name, p_operation, get_current_tenant_id(), p_row_tenant_id, p_details);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================
-- Enable RLS on Workers Table
-- ============================================

ALTER TABLE workers ENABLE ROW LEVEL SECURITY;
ALTER TABLE workers FORCE ROW LEVEL SECURITY;

-- Drop existing policies if they exist (for idempotency)
DROP POLICY IF EXISTS tenant_isolation_workers_select ON workers;
DROP POLICY IF EXISTS tenant_isolation_workers_insert ON workers;
DROP POLICY IF EXISTS tenant_isolation_workers_update ON workers;
DROP POLICY IF EXISTS tenant_isolation_workers_delete ON workers;

-- SELECT policy: Can only see rows belonging to current tenant or if no tenant context set
CREATE POLICY tenant_isolation_workers_select ON workers
    FOR SELECT
    USING (
        tenant_id = get_current_tenant_id()
        OR get_current_tenant_id() IS NULL
        OR tenant_id IS NULL  -- Allow access to legacy rows without tenant_id
    );

-- INSERT policy: Can only insert rows for current tenant
CREATE POLICY tenant_isolation_workers_insert ON workers
    FOR INSERT
    WITH CHECK (
        tenant_id = get_current_tenant_id()
        OR get_current_tenant_id() IS NULL
        OR tenant_id IS NULL
    );

-- UPDATE policy: Can only update rows belonging to current tenant
CREATE POLICY tenant_isolation_workers_update ON workers
    FOR UPDATE
    USING (
        tenant_id = get_current_tenant_id()
        OR get_current_tenant_id() IS NULL
        OR tenant_id IS NULL
    )
    WITH CHECK (
        tenant_id = get_current_tenant_id()
        OR get_current_tenant_id() IS NULL
        OR tenant_id IS NULL
    );

-- DELETE policy: Can only delete rows belonging to current tenant
CREATE POLICY tenant_isolation_workers_delete ON workers
    FOR DELETE
    USING (
        tenant_id = get_current_tenant_id()
        OR get_current_tenant_id() IS NULL
        OR tenant_id IS NULL
    );

-- Admin bypass policy
DROP POLICY IF EXISTS admin_bypass_workers ON workers;
CREATE POLICY admin_bypass_workers ON workers
    FOR ALL
    TO a2a_admin
    USING (true)
    WITH CHECK (true);

-- RLS enabled on workers table

-- ============================================
-- Enable RLS on Codebases Table
-- ============================================

ALTER TABLE codebases ENABLE ROW LEVEL SECURITY;
ALTER TABLE codebases FORCE ROW LEVEL SECURITY;

-- Drop existing policies if they exist
DROP POLICY IF EXISTS tenant_isolation_codebases_select ON codebases;
DROP POLICY IF EXISTS tenant_isolation_codebases_insert ON codebases;
DROP POLICY IF EXISTS tenant_isolation_codebases_update ON codebases;
DROP POLICY IF EXISTS tenant_isolation_codebases_delete ON codebases;

-- SELECT policy
CREATE POLICY tenant_isolation_codebases_select ON codebases
    FOR SELECT
    USING (
        tenant_id = get_current_tenant_id()
        OR get_current_tenant_id() IS NULL
        OR tenant_id IS NULL
    );

-- INSERT policy
CREATE POLICY tenant_isolation_codebases_insert ON codebases
    FOR INSERT
    WITH CHECK (
        tenant_id = get_current_tenant_id()
        OR get_current_tenant_id() IS NULL
        OR tenant_id IS NULL
    );

-- UPDATE policy
CREATE POLICY tenant_isolation_codebases_update ON codebases
    FOR UPDATE
    USING (
        tenant_id = get_current_tenant_id()
        OR get_current_tenant_id() IS NULL
        OR tenant_id IS NULL
    )
    WITH CHECK (
        tenant_id = get_current_tenant_id()
        OR get_current_tenant_id() IS NULL
        OR tenant_id IS NULL
    );

-- DELETE policy
CREATE POLICY tenant_isolation_codebases_delete ON codebases
    FOR DELETE
    USING (
        tenant_id = get_current_tenant_id()
        OR get_current_tenant_id() IS NULL
        OR tenant_id IS NULL
    );

-- Admin bypass policy
DROP POLICY IF EXISTS admin_bypass_codebases ON codebases;
CREATE POLICY admin_bypass_codebases ON codebases
    FOR ALL
    TO a2a_admin
    USING (true)
    WITH CHECK (true);

-- RLS enabled on codebases table

-- ============================================
-- Enable RLS on Tasks Table
-- ============================================

ALTER TABLE tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE tasks FORCE ROW LEVEL SECURITY;

-- Drop existing policies if they exist
DROP POLICY IF EXISTS tenant_isolation_tasks_select ON tasks;
DROP POLICY IF EXISTS tenant_isolation_tasks_insert ON tasks;
DROP POLICY IF EXISTS tenant_isolation_tasks_update ON tasks;
DROP POLICY IF EXISTS tenant_isolation_tasks_delete ON tasks;

-- SELECT policy
CREATE POLICY tenant_isolation_tasks_select ON tasks
    FOR SELECT
    USING (
        tenant_id = get_current_tenant_id()
        OR get_current_tenant_id() IS NULL
        OR tenant_id IS NULL
    );

-- INSERT policy
CREATE POLICY tenant_isolation_tasks_insert ON tasks
    FOR INSERT
    WITH CHECK (
        tenant_id = get_current_tenant_id()
        OR get_current_tenant_id() IS NULL
        OR tenant_id IS NULL
    );

-- UPDATE policy
CREATE POLICY tenant_isolation_tasks_update ON tasks
    FOR UPDATE
    USING (
        tenant_id = get_current_tenant_id()
        OR get_current_tenant_id() IS NULL
        OR tenant_id IS NULL
    )
    WITH CHECK (
        tenant_id = get_current_tenant_id()
        OR get_current_tenant_id() IS NULL
        OR tenant_id IS NULL
    );

-- DELETE policy
CREATE POLICY tenant_isolation_tasks_delete ON tasks
    FOR DELETE
    USING (
        tenant_id = get_current_tenant_id()
        OR get_current_tenant_id() IS NULL
        OR tenant_id IS NULL
    );

-- Admin bypass policy
DROP POLICY IF EXISTS admin_bypass_tasks ON tasks;
CREATE POLICY admin_bypass_tasks ON tasks
    FOR ALL
    TO a2a_admin
    USING (true)
    WITH CHECK (true);

-- RLS enabled on tasks table

-- ============================================
-- Enable RLS on Sessions Table
-- ============================================

ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions FORCE ROW LEVEL SECURITY;

-- Drop existing policies if they exist
DROP POLICY IF EXISTS tenant_isolation_sessions_select ON sessions;
DROP POLICY IF EXISTS tenant_isolation_sessions_insert ON sessions;
DROP POLICY IF EXISTS tenant_isolation_sessions_update ON sessions;
DROP POLICY IF EXISTS tenant_isolation_sessions_delete ON sessions;

-- SELECT policy
CREATE POLICY tenant_isolation_sessions_select ON sessions
    FOR SELECT
    USING (
        tenant_id = get_current_tenant_id()
        OR get_current_tenant_id() IS NULL
        OR tenant_id IS NULL
    );

-- INSERT policy
CREATE POLICY tenant_isolation_sessions_insert ON sessions
    FOR INSERT
    WITH CHECK (
        tenant_id = get_current_tenant_id()
        OR get_current_tenant_id() IS NULL
        OR tenant_id IS NULL
    );

-- UPDATE policy
CREATE POLICY tenant_isolation_sessions_update ON sessions
    FOR UPDATE
    USING (
        tenant_id = get_current_tenant_id()
        OR get_current_tenant_id() IS NULL
        OR tenant_id IS NULL
    )
    WITH CHECK (
        tenant_id = get_current_tenant_id()
        OR get_current_tenant_id() IS NULL
        OR tenant_id IS NULL
    );

-- DELETE policy
CREATE POLICY tenant_isolation_sessions_delete ON sessions
    FOR DELETE
    USING (
        tenant_id = get_current_tenant_id()
        OR get_current_tenant_id() IS NULL
        OR tenant_id IS NULL
    );

-- Admin bypass policy
DROP POLICY IF EXISTS admin_bypass_sessions ON sessions;
CREATE POLICY admin_bypass_sessions ON sessions
    FOR ALL
    TO a2a_admin
    USING (true)
    WITH CHECK (true);

-- RLS enabled on sessions table

-- ============================================
-- Create RLS Status View
-- ============================================

CREATE OR REPLACE VIEW rls_status AS
SELECT 
    n.nspname as schemaname,
    c.relname as tablename,
    c.relrowsecurity as rls_enabled,
    c.relforcerowsecurity as rls_forced
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public'
AND c.relkind = 'r'
AND c.relname IN ('workers', 'codebases', 'tasks', 'sessions', 'tenants');

COMMENT ON VIEW rls_status IS 
'View showing RLS status for all tenant-scoped tables.
Use: SELECT * FROM rls_status;';

-- ============================================
-- Create migration tracking table
-- ============================================

CREATE TABLE IF NOT EXISTS schema_migrations (
    id SERIAL PRIMARY KEY,
    migration_name TEXT NOT NULL UNIQUE,
    applied_at TIMESTAMPTZ DEFAULT NOW(),
    checksum TEXT
);

-- Record this migration
INSERT INTO schema_migrations (migration_name, checksum)
VALUES ('enable_rls', md5('enable_rls'))
ON CONFLICT (migration_name) DO UPDATE SET applied_at = NOW();

-- ============================================
-- Grant permissions
-- ============================================

-- Grant usage on functions
GRANT EXECUTE ON FUNCTION get_current_tenant_id() TO PUBLIC;
GRANT EXECUTE ON FUNCTION log_rls_access(TEXT, TEXT, TEXT, JSONB) TO PUBLIC;

-- Grant select on status view
GRANT SELECT ON rls_status TO PUBLIC;

-- ============================================
-- Commit transaction
-- ============================================

COMMIT;

-- ============================================
-- Summary output
-- ============================================

DO $$
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '============================================';
    RAISE NOTICE 'RLS Migration Complete';
    RAISE NOTICE '============================================';
    RAISE NOTICE 'Tables with RLS enabled:';
    RAISE NOTICE '  - workers';
    RAISE NOTICE '  - codebases';
    RAISE NOTICE '  - tasks';
    RAISE NOTICE '  - sessions';
    RAISE NOTICE '';
    RAISE NOTICE 'To use RLS in your application:';
    RAISE NOTICE '  SET app.current_tenant_id = ''your-tenant-id'';';
    RAISE NOTICE '  -- run your queries --';
    RAISE NOTICE '  RESET app.current_tenant_id;';
    RAISE NOTICE '';
    RAISE NOTICE 'To check RLS status:';
    RAISE NOTICE '  SELECT * FROM rls_status;';
    RAISE NOTICE '';
    RAISE NOTICE 'To rollback:';
    RAISE NOTICE '  Run disable_rls.sql';
    RAISE NOTICE '============================================';
END $$;
