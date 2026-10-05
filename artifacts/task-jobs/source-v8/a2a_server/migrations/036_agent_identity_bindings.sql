BEGIN;

CREATE TABLE IF NOT EXISTS agent_identity_bindings (
    id BIGSERIAL PRIMARY KEY,
    provisioning_id TEXT NOT NULL UNIQUE,
    persona_id TEXT NOT NULL,
    spiffe_id TEXT NOT NULL UNIQUE,
    keycloak_subject TEXT NOT NULL UNIQUE,
    keycloak_realm TEXT NOT NULL,
    tenant_id TEXT REFERENCES tenants(id) ON DELETE RESTRICT,
    roles TEXT[] NOT NULL,
    groups TEXT[] NOT NULL,
    policy_binding_id TEXT NOT NULL UNIQUE,
    policy_revision TEXT NOT NULL,
    provenance_id TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_identity_binding_tenant
    ON agent_identity_bindings(tenant_id);

COMMENT ON TABLE agent_identity_bindings IS
'Immutable SPIFFE authentication to Keycloak and OPA authority bindings.';

COMMIT;
