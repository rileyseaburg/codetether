"""Typed response parsing for Forgejo verification."""

import httpx


async def response_json(
    client: httpx.AsyncClient, url: str
) -> dict[str, object]:
    """Fetch one required Forgejo object or fail closed."""
    response = await client.get(url)
    response.raise_for_status()
    value = response.json()
    if not isinstance(value, dict):
        raise ValueError('Forgejo verification response is invalid')
    return value


def nested(value: object, *keys: str) -> object:
    """Read a nested response field without loose dynamic typing."""
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value
