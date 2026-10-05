"""Keycloak identity-plane orchestration for one agent workload."""

from a2a_server.agent_identity_claims import managed_roles
from a2a_server.agent_identity_errors import IdentityConfigurationError
from a2a_server.agent_identity_types import KeycloakIdentity, WorkloadIdentity
from a2a_server.keycloak_agent_account import ensure_account
from a2a_server.keycloak_agent_groups import ensure_groups
from a2a_server.keycloak_agent_roles import sync_roles
from a2a_server.keycloak_provisioner_config import KeycloakProvisionerConfig
from a2a_server.keycloak_provisioner_http import KeycloakAdminClient


async def provision_keycloak(
    realm: str,
    workload: WorkloadIdentity,
    display_name: str,
    roles: list[str],
    groups: list[str],
) -> KeycloakIdentity:
    """Create the subject, assign exact managed roles, and add its groups."""
    config = KeycloakProvisionerConfig.from_env()
    if realm != config.managed_realm:
        raise IdentityConfigurationError(
            'requested Keycloak realm is not managed'
        )
    api = KeycloakAdminClient(config)
    identity = await ensure_account(api, realm, workload, display_name)
    await sync_roles(api, realm, identity.subject, roles, managed_roles())
    await ensure_groups(api, realm, identity.subject, groups)
    return identity
