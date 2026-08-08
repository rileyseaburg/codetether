"""Converged identity-plane values used to build an API response."""

from dataclasses import dataclass

from a2a_server.agent_identity_api_types import ProvisionAgentIdentityRequest
from a2a_server.agent_identity_types import KeycloakIdentity, WorkloadIdentity


@dataclass(frozen=True)
class IdentityPlaneResult:
    """Values returned after every durable plane has converged."""

    request: ProvisionAgentIdentityRequest
    workload: WorkloadIdentity
    subject: KeycloakIdentity
    roles: list[str]
    groups: list[str]
    receipt: dict[str, object]
    forgejo: dict[str, object]
