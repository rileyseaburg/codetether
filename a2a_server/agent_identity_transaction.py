"""Ordered convergence transaction for all agent identity planes."""

from a2a_server.agent_identity_api_types import (
    ProvisionAgentIdentityRequest,
    ProvisionedAgentIdentity,
)
from a2a_server.agent_identity_claims import normalize
from a2a_server.agent_identity_dependencies import (
    BindingWriter,
    KeycloakProvisioner,
    ReceiptProjector,
    WorkloadProvisioner,
)
from a2a_server.agent_identity_names import workload_identity
from a2a_server.agent_identity_receipt import build_receipt
from a2a_server.agent_identity_response import build_response
from a2a_server.agent_identity_result import IdentityPlaneResult


async def converge(
    request: ProvisionAgentIdentityRequest,
    workload: WorkloadProvisioner,
    keycloak: KeycloakProvisioner,
    binding: BindingWriter,
    forgejo: ReceiptProjector,
) -> ProvisionedAgentIdentity:
    """Converge dependencies before publishing the final receipt."""
    roles, groups = normalize(request.realm_roles, request.groups)
    identity = workload_identity(request.provisioning_id, request.persona_id)
    await workload(identity, request.persona_id, request.provisioning_id)
    subject = await keycloak(
        request.realm_name, identity, request.display_name, roles, groups
    )
    receipt = build_receipt(request, identity, subject, roles, groups)
    await binding(receipt)
    forgejo_receipt = await forgejo(receipt)
    result = IdentityPlaneResult(
        request, identity, subject, roles, groups, receipt, forgejo_receipt
    )
    return build_response(result)
