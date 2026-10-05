"""Organizational Keycloak group membership for agent workloads."""

from a2a_server.keycloak_group_lookup import ensure_group
from a2a_server.keycloak_provisioner_http import KeycloakAdminClient


async def ensure_groups(
    api: KeycloakAdminClient, realm: str, subject: str, groups: list[str]
) -> None:
    """Ensure requested groups exist and include the service account."""
    base = f'/admin/realms/{realm}/users/{subject}/groups'
    current = (await api.request('GET', base, {200})).json()
    for group in current:
        if group.get('name') not in groups:
            await api.request('DELETE', f'{base}/{group["id"]}', {204})
    for name in groups:
        group_id = await ensure_group(api, realm, name)
        await api.request('PUT', f'{base}/{group_id}', {204})
