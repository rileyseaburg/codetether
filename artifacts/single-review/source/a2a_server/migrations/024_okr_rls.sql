-- ============================================
-- RLS for OKR Tables (okrs, okr_key_results, okr_runs)
-- ============================================
-- Follows the same pattern as enable_rls.sql and 010_task_runs_tenant_isolation.sql
-- Uses get_current_tenant_id() helper function and app.current_tenant_id session var.
-- Creates the helper function if it doesn't already exist.

BEGIN;

-- ============================================
-- Prerequisites: roles and helper function
-- ============================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'a2a_admin') THEN
        CREATE ROLE a2a_admin NOLOGIN;
    END IF;
END $$;

CREATE OR REPLACE FUNCTION get_current_tenant_id()
RETURNS TEXT AS $$
DECLARE
    tenant_id TEXT;
BEGIN
    tenant_id := current_setting('app.current_tenant_id', true);
    IF tenant_id IS NULL OR tenant_id = '' THEN
        RETURN NULL;
    END IF;
    RETURN tenant_id;
EXCEPTION
    WHEN OTHERS THEN
        RETURN NULL;
END;
$$ LANGUAGE plpgsql STABLE SECURITY DEFINER;

-- ============================================
-- Enable RLS on okrs table
-- ============================================

ALTER TABLE okrs ENABLE ROW LEVEL SECURITY;
ALTER TABLE okrs FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_okrs_select ON okrs;
DROP POLICY IF EXISTS tenant_isolation_okrs_insert ON okrs;
DROP POLICY IF EXISTS tenant_isolation_okrs_update ON okrs;
DROP POLICY IF EXISTS tenant_isolation_okrs_delete ON okrs;

CREATE POLICY tenant_isolation_okrs_select ON okrs
    FOR SELECT
    USING (
        tenant_id = get_current_tenant_id()
        OR get_current_tenant_id() IS NULL
        OR tenant_id IS NULL
    );

CREATE POLICY tenant_isolation_okrs_insert ON okrs
    FOR INSERT
    WITH CHECK (
        tenant_id = get_current_tenant_id()
        OR get_current_tenant_id() IS NULL
        OR tenant_id IS NULL
    );

CREATE POLICY tenant_isolation_okrs_update ON okrs
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

CREATE POLICY tenant_isolation_okrs_delete ON okrs
    FOR DELETE
    USING (
        tenant_id = get_current_tenant_id()
        OR get_current_tenant_id() IS NULL
        OR tenant_id IS NULL
    );

DROP POLICY IF EXISTS admin_bypass_okrs ON okrs;
CREATE POLICY admin_bypass_okrs ON okrs
    FOR ALL
    TO a2a_admin
    USING (true)
    WITH CHECK (true);

-- ============================================
-- Enable RLS on okr_key_results table
-- ============================================

ALTER TABLE okr_key_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE okr_key_results FORCE ROW LEVEL SECURITY;

-- okr_key_results doesn't have its own tenant_id — they inherit isolation
-- through the FK to okrs. We use a subquery policy to enforce this.

DROP POLICY IF EXISTS tenant_isolation_okr_kr_select ON okr_key_results;
DROP POLICY IF EXISTS tenant_isolation_okr_kr_insert ON okr_key_results;
DROP POLICY IF EXISTS tenant_isolation_okr_kr_update ON okr_key_results;
DROP POLICY IF EXISTS tenant_isolation_okr_kr_delete ON okr_key_results;

CREATE POLICY tenant_isolation_okr_kr_select ON okr_key_results
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM okrs
            WHERE okrs.id = okr_key_results.okr_id
              AND (okrs.tenant_id = get_current_tenant_id()
                   OR get_current_tenant_id() IS NULL
                   OR okrs.tenant_id IS NULL)
        )
    );

CREATE POLICY tenant_isolation_okr_kr_insert ON okr_key_results
    FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM okrs
            WHERE okrs.id = okr_key_results.okr_id
              AND (okrs.tenant_id = get_current_tenant_id()
                   OR get_current_tenant_id() IS NULL
                   OR okrs.tenant_id IS NULL)
        )
    );

CREATE POLICY tenant_isolation_okr_kr_update ON okr_key_results
    FOR UPDATE
    USING (
        EXISTS (
            SELECT 1 FROM okrs
            WHERE okrs.id = okr_key_results.okr_id
              AND (okrs.tenant_id = get_current_tenant_id()
                   OR get_current_tenant_id() IS NULL
                   OR okrs.tenant_id IS NULL)
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM okrs
            WHERE okrs.id = okr_key_results.okr_id
              AND (okrs.tenant_id = get_current_tenant_id()
                   OR get_current_tenant_id() IS NULL
                   OR okrs.tenant_id IS NULL)
        )
    );

CREATE POLICY tenant_isolation_okr_kr_delete ON okr_key_results
    FOR DELETE
    USING (
        EXISTS (
            SELECT 1 FROM okrs
            WHERE okrs.id = okr_key_results.okr_id
              AND (okrs.tenant_id = get_current_tenant_id()
                   OR get_current_tenant_id() IS NULL
                   OR okrs.tenant_id IS NULL)
        )
    );

DROP POLICY IF EXISTS admin_bypass_okr_kr ON okr_key_results;
CREATE POLICY admin_bypass_okr_kr ON okr_key_results
    FOR ALL
    TO a2a_admin
    USING (true)
    WITH CHECK (true);

-- ============================================
-- Enable RLS on okr_runs table
-- ============================================

ALTER TABLE okr_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE okr_runs FORCE ROW LEVEL SECURITY;

-- Same inheritance pattern as okr_key_results — isolation via FK to okrs.

DROP POLICY IF EXISTS tenant_isolation_okr_runs_select ON okr_runs;
DROP POLICY IF EXISTS tenant_isolation_okr_runs_insert ON okr_runs;
DROP POLICY IF EXISTS tenant_isolation_okr_runs_update ON okr_runs;
DROP POLICY IF EXISTS tenant_isolation_okr_runs_delete ON okr_runs;

CREATE POLICY tenant_isolation_okr_runs_select ON okr_runs
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM okrs
            WHERE okrs.id = okr_runs.okr_id
              AND (okrs.tenant_id = get_current_tenant_id()
                   OR get_current_tenant_id() IS NULL
                   OR okrs.tenant_id IS NULL)
        )
    );

CREATE POLICY tenant_isolation_okr_runs_insert ON okr_runs
    FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM okrs
            WHERE okrs.id = okr_runs.okr_id
              AND (okrs.tenant_id = get_current_tenant_id()
                   OR get_current_tenant_id() IS NULL
                   OR okrs.tenant_id IS NULL)
        )
    );

CREATE POLICY tenant_isolation_okr_runs_update ON okr_runs
    FOR UPDATE
    USING (
        EXISTS (
            SELECT 1 FROM okrs
            WHERE okrs.id = okr_runs.okr_id
              AND (okrs.tenant_id = get_current_tenant_id()
                   OR get_current_tenant_id() IS NULL
                   OR okrs.tenant_id IS NULL)
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM okrs
            WHERE okrs.id = okr_runs.okr_id
              AND (okrs.tenant_id = get_current_tenant_id()
                   OR get_current_tenant_id() IS NULL
                   OR okrs.tenant_id IS NULL)
        )
    );

CREATE POLICY tenant_isolation_okr_runs_delete ON okr_runs
    FOR DELETE
    USING (
        EXISTS (
            SELECT 1 FROM okrs
            WHERE okrs.id = okr_runs.okr_id
              AND (okrs.tenant_id = get_current_tenant_id()
                   OR get_current_tenant_id() IS NULL
                   OR okrs.tenant_id IS NULL)
        )
    );

DROP POLICY IF EXISTS admin_bypass_okr_runs ON okr_runs;
CREATE POLICY admin_bypass_okr_runs ON okr_runs
    FOR ALL
    TO a2a_admin
    USING (true)
    WITH CHECK (true);

-- ============================================
-- Update rls_status view
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
AND c.relname IN (
    'workers', 'workspaces', 'tasks', 'sessions', 'tenants',
    'task_runs', 'okrs', 'okr_key_results', 'okr_runs'
);

-- Record migration
CREATE TABLE IF NOT EXISTS schema_migrations (
    id SERIAL PRIMARY KEY,
    migration_name TEXT NOT NULL UNIQUE,
    applied_at TIMESTAMPTZ DEFAULT NOW(),
    checksum TEXT
);

INSERT INTO schema_migrations (migration_name, checksum)
VALUES ('024_okr_rls', md5('024_okr_rls'))
ON CONFLICT (migration_name) DO UPDATE SET applied_at = NOW();

COMMIT;
