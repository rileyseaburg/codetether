"""GitHub App authentication and REST helpers."""

import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx
import jwt
from fastapi import HTTPException

from .settings import get_secret


async def verify_signature(signature: str, body: bytes) -> None:
    """Reject webhook deliveries whose HMAC does not match GitHub's header."""
    secret = await get_secret('webhook_secret', 'GITHUB_WEBHOOK_SECRET', 'webhook_secret', 'github_webhook_secret')
    if not secret:
        raise HTTPException(status_code=503, detail='GitHub webhook secret is not configured')
    expected = f"sha256={hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()}"
    if not signature or not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=401, detail='Invalid GitHub webhook signature')


async def installation_token(installation_id: int) -> tuple[str, Optional[str]]:
    """Mint a short-lived installation token for REST and Git operations."""
    app_id = await get_secret('app_id', 'GITHUB_APP_ID', 'app_id', 'github_app_id')
    private_key = await get_secret('private_key', 'GITHUB_APP_PRIVATE_KEY', 'private_key', 'github_app_private_key')
    if not app_id or not private_key:
        raise HTTPException(status_code=503, detail='GitHub App credentials are not configured')
    now = datetime.now(timezone.utc)
    encoded = jwt.encode({'iat': int((now - timedelta(seconds=30)).timestamp()), 'exp': int((now + timedelta(minutes=9)).timestamp()), 'iss': app_id}, private_key, algorithm='RS256')
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f'https://api.github.com/app/installations/{installation_id}/access_tokens',
            headers={'Accept': 'application/vnd.github+json', 'Authorization': f'Bearer {encoded}', 'X-GitHub-Api-Version': '2022-11-28'},
        )
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail=f'GitHub App token mint failed: {response.text[:400]}')
    data = response.json()
    return data['token'], data.get('expires_at')


async def github_json(method: str, path: str, token: str, payload: Optional[dict[str, Any]] = None) -> Any:
    """Call the GitHub REST API with an installation token."""
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.request(
            method,
            f'https://api.github.com{path}',
            headers={'Accept': 'application/vnd.github+json', 'Authorization': f'Bearer {token}', 'User-Agent': 'codetether-github-app', 'X-GitHub-Api-Version': '2022-11-28'},
            json=payload,
        )
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail=f'GitHub API {method} {path} failed: {response.text[:400]}')
    return response.json() if response.content else {}
