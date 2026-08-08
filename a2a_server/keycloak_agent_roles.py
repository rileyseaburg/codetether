"""Exact OPA-managed realm-role projection into Keycloak."""

from http import HTTPStatus

from a2a_server.keycloak_provisioner_http import KeycloakAdminClient


async def sync_roles(
    api: KeycloakAdminClient,
    realm: str,
    subject: str,
    desired: list[str],
    managed: list[str],
) -> None:
    """Add desired roles and remove only undesired OPA-managed roles."""
    base = f'/admin/realms/{realm}'
    role_objects: dict[str, dict[str, object]] = {}
    for role in managed:
        response = await api.request('GET', f'{base}/roles/{role}', {200, 404})
        if response.status_code == HTTPStatus.NOT_FOUND:
            await api.request(
                'POST',
                f'{base}/roles',
                {201, 409},
                json={
                    'name': role,
                    'description': f'OPA workload role: {role}',
                },
            )
            response = await api.request('GET', f'{base}/roles/{role}', {200})
        role_objects[role] = response.json()
    path = f'{base}/users/{subject}/role-mappings/realm'
    current = {
        role['name']: role
        for role in (await api.request('GET', path, {200})).json()
        if role.get('name')
    }
    remove = [
        current[role]
        for role in managed
        if role in current and role not in desired
    ]
    add = [role_objects[role] for role in desired if role not in current]
    if remove:
        await api.request('DELETE', path, {204}, json=remove)
    if add:
        await api.request('POST', path, {204}, json=add)
