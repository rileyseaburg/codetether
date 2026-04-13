"""Runtime settings for GitHub App automation."""

import os
from typing import Optional

_SECRET_CACHE: dict[str, Optional[str]] = {}
_VAULT_PATHS = ('codetether/github_app', 'codetether/github-app')

APP_SLUG = os.environ.get('GITHUB_APP_SLUG', 'codetether').strip() or 'codetether'
MODEL_REF = os.environ.get('GITHUB_APP_MODEL_REF', 'zai:glm-5.1').strip() or 'zai:glm-5.1'
TARGET_AGENT = os.environ.get('GITHUB_APP_TARGET_AGENT', 'knative-worker').strip() or 'knative-worker'
TARGET_WORKER_ID = os.environ.get('GITHUB_APP_TARGET_WORKER_ID', '').strip()
PREFERRED_AGENTS = tuple(
    part.strip()
    for part in os.environ.get(
        'GITHUB_APP_PREFERRED_AGENTS',
        'ubuntu-dev,knative-worker',
    ).split(',')
    if part.strip()
)


async def get_secret(name: str, env_key: str, *keys: str) -> Optional[str]:
    """Resolve a GitHub App secret from env first, then Vault."""
    if name in _SECRET_CACHE:
        return _SECRET_CACHE[name]
    value = os.environ.get(env_key, '').strip()
    if value:
        _SECRET_CACHE[name] = value
        return value
    try:
        from ..vault_client import get_vault_client

        client = get_vault_client()
        for path in _VAULT_PATHS:
            secret = await client.read_secret(path)
            if not secret:
                continue
            for key in keys:
                value = str(secret.get(key, '')).strip()
                if value:
                    _SECRET_CACHE[name] = value
                    return value
    except Exception:
        pass
    _SECRET_CACHE[name] = None
    return None
