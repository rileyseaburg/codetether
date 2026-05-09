from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
import pytest

from a2a_server.opencode_deprecated import router


@pytest.mark.asyncio
async def test_opencode_routes_return_deprecated_gone_response():
    app = FastAPI()
    app.include_router(router)
    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport, base_url='http://test'
    ) as client:
        response = await client.post(
            '/v1/opencode/workers/register',
            json={'worker_id': 'legacy-worker'},
        )

    assert response.status_code == 410
    assert response.headers['Deprecation'] == 'true'
    assert response.headers['Sunset'] == 'Wed, 06 May 2026 00:00:00 GMT'
    assert response.headers['Link'] == '</v1/agent>; rel="successor-version"'
    assert response.json() == {
        'error': 'deprecated_api_gone',
        'message': (
            'The /v1/opencode API has been removed. '
            'Use the CodeTether /v1/agent API instead.'
        ),
        'path': '/v1/opencode/workers/register',
        'replacement_base': '/v1/agent',
    }


def test_opencode_routes_are_marked_deprecated_in_openapi():
    app = FastAPI()
    app.include_router(router)

    operation = app.openapi()['paths']['/v1/opencode/{path}']['post']

    assert operation['deprecated'] is True
