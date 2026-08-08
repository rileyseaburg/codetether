"""Immutable Forgejo projection receipt for a provisioned agent identity."""

import hashlib

from a2a_server.agent_identity_api_types import ProvisionAgentIdentityRequest
from a2a_server.agent_identity_policy import policy_binding, policy_revision
from a2a_server.agent_identity_types import KeycloakIdentity, WorkloadIdentity


def build_receipt(
    request: ProvisionAgentIdentityRequest,
    workload: WorkloadIdentity,
    keycloak: KeycloakIdentity,
    roles: list[str],
    groups: list[str],
) -> dict[str, object]:
    """Build the exact receipt accepted by Forgejo's SPIFFE bridge API."""
    trace = hashlib.sha256(request.provisioning_id.encode()).hexdigest()[:32]
    return {
        'provisioning_id': request.provisioning_id,
        'persona_id': request.persona_id,
        'spiffe_id': workload.spiffe_id,
        'keycloak_subject': keycloak.subject,
        'username': workload.username,
        'display_name': request.display_name,
        'email': workload.email,
        'keycloak_realm': request.realm_name,
        'realm_roles': roles,
        'groups': groups,
        'opa_policy_binding_id': policy_binding(
            workload.spiffe_id, keycloak.subject
        ),
        'opa_policy_revision': policy_revision(),
        'provenance_id': f'ctprov_{trace}',
    }
