"""Durable SPIFFE-to-Keycloak-to-OPA identity binding."""

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentIdentityBinding:
    """One verified workload identity and its explicit authority snapshot."""

    provisioning_id: str
    persona_id: str
    spiffe_id: str
    keycloak_subject: str
    keycloak_realm: str
    roles: list[str]
    groups: list[str]
    policy_binding_id: str
    policy_revision: str
    provenance_id: str
    tenant_id: str | None = None

    def policy_user(self) -> dict[str, object]:
        """Build the identity document evaluated by OPA."""
        return {
            'user_id': self.spiffe_id,
            'sub': self.spiffe_id,
            'roles': self.roles,
            'tenant_id': self.tenant_id,
            'scopes': [],
            'auth_source': 'spiffe',
            'spiffe_id': self.spiffe_id,
            'keycloak_sub': self.keycloak_subject,
            'realm_name': self.keycloak_realm,
            'persona_id': self.persona_id,
            'provenance_id': self.provenance_id,
        }
