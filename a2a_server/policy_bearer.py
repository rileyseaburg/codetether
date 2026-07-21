"""Bearer-token extraction shared by policy identity resolvers."""

from fastapi import Request


def token(request: Request) -> str | None:
    """Read a Bearer token or the EventSource query-string fallback."""
    header = request.headers.get('Authorization')
    if header and header.startswith('Bearer '):
        return header[7:]
    return request.query_params.get('access_token')
