"""SQL statements for immutable workload-authority bindings."""

INSERT = """
INSERT INTO agent_identity_bindings (
  provisioning_id, persona_id, spiffe_id, keycloak_subject, keycloak_realm,
  roles, groups, policy_binding_id, policy_revision, provenance_id, tenant_id
) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,
  (SELECT id FROM tenants WHERE realm_name = $5 LIMIT 1))
ON CONFLICT DO NOTHING
"""

SELECT_ANY = """
SELECT provisioning_id, persona_id, spiffe_id, keycloak_subject,
       keycloak_realm, roles, groups, policy_binding_id, policy_revision,
       provenance_id, tenant_id
FROM agent_identity_bindings
WHERE provisioning_id = $1 OR spiffe_id = $2 OR keycloak_subject = $3
LIMIT 1
"""

SELECT_SPIFFE = """
SELECT provisioning_id, persona_id, spiffe_id, keycloak_subject,
       keycloak_realm, roles, groups, policy_binding_id, policy_revision,
       provenance_id, tenant_id
FROM agent_identity_bindings WHERE spiffe_id = $1
"""
