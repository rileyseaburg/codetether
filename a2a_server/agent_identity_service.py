"""Retry-safe orchestration of the agent workload identity plane."""

from dataclasses import dataclass

from a2a_server.agent_identity_api_types import (
    ProvisionAgentIdentityRequest,
    ProvisionedAgentIdentity,
)
from a2a_server.agent_identity_dependencies import (
    BindingWriter,
    KeycloakProvisioner,
    ReceiptProjector,
    WorkloadProvisioner,
)
from a2a_server.agent_identity_forgejo import project_receipt
from a2a_server.agent_identity_kubernetes import ensure_service_account
from a2a_server.agent_identity_repository import save_binding
from a2a_server.agent_identity_transaction import converge
from a2a_server.keycloak_agent_provisioner import provision_keycloak


@dataclass(frozen=True)
class IdentityProvisioner:
    """Explicit dependency bundle for one identity transaction."""

    workload: WorkloadProvisioner = ensure_service_account
    keycloak: KeycloakProvisioner = provision_keycloak
    binding: BindingWriter = save_binding
    forgejo: ReceiptProjector = project_receipt

    async def provision(
        self, request: ProvisionAgentIdentityRequest
    ) -> ProvisionedAgentIdentity:
        """Run the retry-safe identity-plane transaction."""
        return await converge(
            request, self.workload, self.keycloak, self.binding, self.forgejo
        )
