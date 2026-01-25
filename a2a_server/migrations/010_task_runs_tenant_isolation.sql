-- Migration: Add tenant isolation to task_runs table
-- This adds tenant_id column and RLS policies for multi-tenant isolation

-- ============================================
-- Create admin role if it doesn't exist
-- ============================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'a2a_admin') THEN
        CREATE ROLE a2a_admin NOLOGIN;
    END IF;
END $$;

-- ============================================
-- Add tenant_id column to task_runs
-- ============================================

ALTER TABLE task_runs 
    ADD COLUMN IF NOT EXISTS tenant_id TEXT REFERENCES tenants(id);

-- Create index for efficient tenant filtering
CREATE INDEX IF NOT EXISTS idx_task_runs_tenant ON task_runs(tenant_id);

-- Composite index for tenant + status queries
CREATE INDEX IF NOT EXISTS idx_task_runs_tenant_status 
    ON task_runs(tenant_id, status, created_at DESC);

-- ============================================
-- Enable RLS on task_runs table
-- ============================================

ALTER TABLE task_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE task_runs FORCE ROW LEVEL SECURITY;

-- Drop existing policies if they exist (for idempotency)
DROP POLICY IF EXISTS tenant_isolation_task_runs_select ON task_runs;
DROP POLICY IF EXISTS tenant_isolation_task_runs_insert ON task_runs;
DROP POLICY IF EXISTS tenant_isolation_task_runs_update ON task_runs;
DROP POLICY IF EXISTS tenant_isolation_task_runs_delete ON task_runs;

-- SELECT policy: Can only see rows belonging to current tenant or if no tenant context set
CREATE POLICY tenant_isolation_task_runs_select ON task_runs
    FOR SELECT
    USING (
        tenant_id = get_current_tenant_id()
        OR get_current_tenant_id() IS NULL
        OR tenant_id IS NULL  -- Allow access to legacy rows without tenant_id
    );

-- INSERT policy: Can only insert rows for current tenant
CREATE POLICY tenant_isolation_task_runs_insert ON task_runs
    FOR INSERT
    WITH CHECK (
        tenant_id = get_current_tenant_id()
        OR get_current_tenant_id() IS NULL
        OR tenant_id IS NULL
    );

-- UPDATE policy: Can only update rows belonging to current tenant
CREATE POLICY tenant_isolation_task_runs_update ON task_runs
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
CREATE POLICY tenant_isolation_task_runs_delete ON task_runs
    FOR DELETE
    USING (
        tenant_id = get_current_tenant_id()
        OR get_current_tenant_id() IS NULL
        OR tenant_id IS NULL
    );

-- Admin bypass policy
DROP POLICY IF EXISTS admin_bypass_task_runs ON task_runs;
CREATE POLICY admin_bypass_task_runs ON task_runs
    FOR ALL
    TO a2a_admin
    USING (true)
    WITH CHECK (true);

-- ============================================
-- Update claim_next_task_run function for tenant isolation
-- ============================================

CREATE OR REPLACE FUNCTION claim_next_task_run(
    p_worker_id TEXT,
    p_lease_duration_seconds INTEGER DEFAULT 600,
    p_tenant_id TEXT DEFAULT NULL
)
RETURNS TABLE (
    run_id TEXT,
    task_id TEXT,
    user_id TEXT,
    priority INTEGER,
    tenant_id TEXT
) AS $$
DECLARE
    v_run task_runs%ROWTYPE;
BEGIN
    -- Find next queued job, respecting user concurrency limits and tenant isolation
    SELECT tr.* INTO v_run
    FROM task_runs tr
    LEFT JOIN users u ON tr.user_id = u.id
    WHERE tr.status = 'queued'
      AND (tr.lease_expires_at IS NULL OR tr.lease_expires_at < NOW())
      -- Tenant isolation: only claim tasks for specified tenant or NULL tenant
      AND (p_tenant_id IS NULL OR tr.tenant_id = p_tenant_id OR tr.tenant_id IS NULL)
      -- Check user hasn't hit concurrency limit (if user exists)
      AND (
          u.id IS NULL OR
          (SELECT COUNT(*) 
           FROM task_runs tr2 
           WHERE tr2.user_id = tr.user_id 
             AND tr2.status = 'running'
          ) < COALESCE(u.concurrency_limit, 999)
      )
    ORDER BY tr.priority DESC, tr.created_at ASC
    FOR UPDATE OF tr SKIP LOCKED
    LIMIT 1;
    
    IF v_run.id IS NULL THEN
        RETURN;
    END IF;
    
    -- Claim the job
    UPDATE task_runs SET
        status = 'running',
        lease_owner = p_worker_id,
        lease_expires_at = NOW() + (p_lease_duration_seconds || ' seconds')::INTERVAL,
        started_at = COALESCE(task_runs.started_at, NOW()),
        attempts = task_runs.attempts + 1,
        updated_at = NOW()
    WHERE id = v_run.id;
    
    -- Return claimed job info
    run_id := v_run.id;
    task_id := v_run.task_id;
    user_id := v_run.user_id;
    priority := v_run.priority;
    tenant_id := v_run.tenant_id;
    RETURN NEXT;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- Update rls_status view to include task_runs
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
AND c.relname IN ('workers', 'codebases', 'tasks', 'sessions', 'tenants', 'task_runs');

-- Record migration
INSERT INTO schema_migrations (migration_name, checksum)
VALUES ('010_task_runs_tenant_isolation', md5('010_task_runs_tenant_isolation'))
ON CONFLICT (migration_name) DO UPDATE SET applied_at = NOW();
