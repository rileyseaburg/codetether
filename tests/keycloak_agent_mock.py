"""Stateful Keycloak Admin API mock for workload-identity tests."""

import httpx


def transport() -> httpx.MockTransport:
    """Return a transport covering client, role, and group convergence."""
    state = {'client': False, 'group': False}

    def handler(request: httpx.Request) -> httpx.Response:  # noqa: PLR0911
        path, method = request.url.path, request.method
        if path.endswith('/token'):
            return httpx.Response(200, json={'access_token': 'token'})
        if path.endswith('/clients') and method == 'GET':
            value = (
                [
                    {
                        'id': 'client-1',
                        'serviceAccountsEnabled': True,
                        'attributes': {
                            'codetether.spiffe_id': 'spiffe://td/ns/ns/sa/sa'
                        },
                    }
                ]
                if state['client']
                else []
            )
            return httpx.Response(200, json=value)
        if path.endswith('/clients'):
            state['client'] = True
            return httpx.Response(201)
        if path.endswith('/service-account-user'):
            return httpx.Response(200, json={'id': 'subject-1'})
        if '/roles/' in path and method == 'GET':
            name = path.rsplit('/', 1)[-1]
            return httpx.Response(200, json={'id': name, 'name': name})
        if path.endswith('/role-mappings/realm') and method == 'GET':
            return httpx.Response(200, json=[])
        if path.endswith('/groups') and method == 'GET':
            value = [{'id': 'group-1', 'name': 'engineering'}]
            return httpx.Response(200, json=value if state['group'] else [])
        if path.endswith('/groups'):
            state['group'] = True
            return httpx.Response(201, headers={'Location': '/groups/group-1'})
        return httpx.Response(204)

    return httpx.MockTransport(handler)
