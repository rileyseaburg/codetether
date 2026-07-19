"""Allowlisted Forgejo API endpoint resolution."""

import json
import os

from urllib.parse import urlparse


def api_base(host: str) -> str:
    """Resolve a Forgejo host only through explicit server configuration."""
    configured = _configured_hosts()
    value = configured.get(host.lower())
    if not isinstance(value, str) or not value:
        raise RuntimeError('Forgejo host is not configured for verification')
    parsed = urlparse(value)
    unsafe = (
        parsed.scheme != 'https'
        or parsed.netloc.lower() != host.lower()
        or parsed.username is not None
        or parsed.password is not None
        or bool(parsed.query)
        or bool(parsed.fragment)
    )
    if unsafe:
        raise RuntimeError('Forgejo verification endpoint is unsafe')
    return value.rstrip('/')


def _configured_hosts() -> dict[str, object]:
    raw = os.environ.get('CODETETHER_FORGEJO_API_BASE_URLS', '')
    if raw:
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as error:
            raise RuntimeError(
                'Forgejo host configuration is invalid'
            ) from error
        if isinstance(value, dict):
            return value
        raise RuntimeError('Forgejo host configuration must be an object')
    single = os.environ.get('CODETETHER_FORGEJO_API_BASE_URL', '')
    parsed = urlparse(single)
    return {parsed.netloc.lower(): single} if parsed.hostname else {}
