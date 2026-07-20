"""Idempotent top-level Keycloak group lookup and creation."""

from http import HTTPStatus

from a2a_server.agent_identity_errors import IdentityUpstreamError
from a2a_server.keycloak_provisioner_http import KeycloakAdminClient


async def ensure_group(api: KeycloakAdminClient, realm: str, name: str) -> str:
    """Return the unique group ID, creating the group when absent."""
    path = f'/admin/realms/{realm}/groups'
    params = {'search': name, 'exact': 'true'}
    matches = (await api.request('GET', path, {200}, params=params)).json()
    exact = [group for group in matches if group.get('name') == name]
    if len(exact) == 1:
        return str(exact[0].get('id') or '')
    if len(exact) > 1:
        raise IdentityUpstreamError(f'Keycloak group is ambiguous: {name}')
    response = await api.request('POST', path, {201, 409}, json={'name': name})
    group_id = response.headers.get('Location', '').rsplit('/', 1)[-1]
    if response.status_code == HTTPStatus.CONFLICT:
        matches = (await api.request('GET', path, {200}, params=params)).json()
        group_id = str(
            next(
                (
                    group.get('id')
                    for group in matches
                    if group.get('name') == name
                ),
                '',
            )
        )
    if not group_id:
        raise IdentityUpstreamError(f'Keycloak group has no ID: {name}')
    return group_id
