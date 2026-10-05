"""Deprecated OpenCode compatibility API.

CodeTether replaced the old `/v1/opencode` API surface.  Keep this router
only to give legacy clients an explicit deprecation response instead of a
misleading generic 404.
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse


DEPRECATION_HEADERS = {
    'Deprecation': 'true',
    'Sunset': 'Wed, 06 May 2026 00:00:00 GMT',
    'Link': '</v1/agent>; rel="successor-version"',
}


router = APIRouter(
    prefix='/v1/opencode',
    tags=['deprecated'],
    deprecated=True,
)


def _deprecated_response(request: Request) -> JSONResponse:
    return JSONResponse(
        status_code=410,
        headers=DEPRECATION_HEADERS,
        content={
            'error': 'deprecated_api_gone',
            'message': (
                'The /v1/opencode API has been removed. '
                'Use the CodeTether /v1/agent API instead.'
            ),
            'path': request.url.path,
            'replacement_base': '/v1/agent',
        },
    )


for route_path, route_name in (('', 'root'), ('/{path:path}', 'wildcard')):
    for method in ('GET', 'POST', 'PUT', 'PATCH', 'DELETE'):
        router.add_api_route(
            route_path,
            _deprecated_response,
            methods=[method],
            deprecated=True,
            operation_id=f'deprecated_opencode_{route_name}_{method.lower()}',
            summary='Deprecated OpenCode API',
        )
