"""Administrative HTTP boundary for agent workload identities."""

from fastapi import APIRouter, Depends, status

from a2a_server.agent_identity_api_types import (
    ProvisionAgentIdentityRequest,
    ProvisionedAgentIdentity,
)
from a2a_server.agent_identity_errors import (
    IdentityConfigurationError,
    IdentityConflictError,
    IdentityUpstreamError,
)
from a2a_server.agent_identity_http_error import raise_http
from a2a_server.agent_identity_service import IdentityProvisioner
from a2a_server.keycloak_auth import UserSession, require_admin
from a2a_server.policy import require_permission


router = APIRouter(prefix='/v1/admin', tags=['Admin Agent Identities'])


def get_provisioner() -> IdentityProvisioner:
    """Construct the default production identity provisioner."""
    return IdentityProvisioner()


_ADMIN = Depends(require_admin)
_MANAGE_USERS = Depends(require_permission('admin:manage_users'))
_PROVISIONER = Depends(get_provisioner)


@router.post(
    '/agent-identities',
    response_model=ProvisionedAgentIdentity,
    status_code=status.HTTP_201_CREATED,
)
async def provision_agent_identity(
    request: ProvisionAgentIdentityRequest,
    _: UserSession = _ADMIN,
    __: dict[str, object] = _MANAGE_USERS,
    provisioner: IdentityProvisioner = _PROVISIONER,
) -> ProvisionedAgentIdentity:
    """Provision workload authentication and explicit, non-persona authority."""
    try:
        return await provisioner.provision(request)
    except (
        IdentityConfigurationError,
        IdentityConflictError,
        IdentityUpstreamError,
        ValueError,
    ) as error:
        raise_http(error)
