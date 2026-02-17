-- ============================================
-- RBAC User Role Assignments + RLS
-- ============================================
--
-- Stores OPA-managed role assignments per user/tenant as a Postgres source
-- of truth snapshot synchronized from Keycloak admin operations.
--
-- Security Model:
-- - tenant_id is required for each row
-- - RLS policies enforce tenant isolation via app.current_tenant_id
-- - a2a_admin role retains explicit bypass policy
-- ============================================

BEGIN;

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

CREATE TABLE IF NOT EXISTS rbac_user_roles (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    realm_name TEXT NOT NULL,
    user_id TEXT NOT NULL,
    email TEXT,
    roles TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    source TEXT NOT NULL DEFAULT 'keycloak',
    updated_by TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (tenant_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_rbac_user_roles_tenant
    ON rbac_user_roles(tenant_id);
CREATE INDEX IF NOT EXISTS idx_rbac_user_roles_realm_user
    ON rbac_user_roles(realm_name, user_id);
CREATE INDEX IF NOT EXISTS idx_rbac_user_roles_roles_gin
    ON rbac_user_roles USING GIN (roles);

ALTER TABLE rbac_user_roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE rbac_user_roles FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_rbac_user_roles_select ON rbac_user_roles;
DROP POLICY IF EXISTS tenant_isolation_rbac_user_roles_insert ON rbac_user_roles;
DROP POLICY IF EXISTS tenant_isolation_rbac_user_roles_update ON rbac_user_roles;
DROP POLICY IF EXISTS tenant_isolation_rbac_user_roles_delete ON rbac_user_roles;
DROP POLICY IF EXISTS admin_bypass_rbac_user_roles ON rbac_user_roles;

CREATE POLICY tenant_isolation_rbac_user_roles_select ON rbac_user_roles
    FOR SELECT
    USING (
        tenant_id = get_current_tenant_id()
        OR get_current_tenant_id() IS NULL
        OR tenant_id IS NULL
    );

CREATE POLICY tenant_isolation_rbac_user_roles_insert ON rbac_user_roles
    FOR INSERT
    WITH CHECK (
        tenant_id = get_current_tenant_id()
        OR get_current_tenant_id() IS NULL
        OR tenant_id IS NULL
    );

CREATE POLICY tenant_isolation_rbac_user_roles_update ON rbac_user_roles
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

CREATE POLICY tenant_isolation_rbac_user_roles_delete ON rbac_user_roles
    FOR DELETE
    USING (
        tenant_id = get_current_tenant_id()
        OR get_current_tenant_id() IS NULL
        OR tenant_id IS NULL
    );

CREATE POLICY admin_bypass_rbac_user_roles ON rbac_user_roles
    FOR ALL
    TO a2a_admin
    USING (true)
    WITH CHECK (true);

COMMENT ON TABLE rbac_user_roles IS
'Tenant-scoped snapshot of OPA-managed Keycloak role assignments, protected by RLS.';

COMMIT;
