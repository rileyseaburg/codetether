"""Administrative response assembly for provisioned identities."""

from a2a_server.agent_identity_api_types import ProvisionedAgentIdentity
from a2a_server.agent_identity_result import IdentityPlaneResult


def build_response(result: IdentityPlaneResult) -> ProvisionedAgentIdentity:
    """Return stable coordinates from every converged identity plane."""
    return ProvisionedAgentIdentity(
        provisioning_id=result.request.provisioning_id,
        persona_id=result.request.persona_id,
        namespace=result.workload.namespace,
        service_account=result.workload.service_account,
        spiffe_id=result.workload.spiffe_id,
        keycloak_subject=result.subject.subject,
        realm_roles=result.roles,
        groups=result.groups,
        policy_revision=str(result.receipt['opa_policy_revision']),
        provenance_id=str(result.receipt['provenance_id']),
        forgejo_identity_id=int(result.forgejo['id']),
    )
