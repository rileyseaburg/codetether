"""GitHub App authentication helpers for installation-scoped API access."""

from __future__ import annotations

import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import httpx
import jwt


def github_app_id() -> str:
    return os.environ.get('GITHUB_APP_ID', '').strip()


def github_app_private_key() -> str:
    return os.environ.get('GITHUB_APP_PRIVATE_KEY', '').strip()


def github_api_base_url() -> str:
    return os.environ.get('GITHUB_APP_API_BASE_URL', 'https://api.github.com').rstrip('/')


def github_webhook_secret() -> str:
    return os.environ.get('GITHUB_WEBHOOK_SECRET', '').strip()


def verify_github_webhook_signature(payload: bytes, signature: Optional[str]) -> bool:
    secret = github_webhook_secret()
    if not secret or not signature:
        return False
    digest = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, f'sha256={digest}')


def build_github_app_jwt() -> str:
    issued_at = datetime.now(timezone.utc)
    payload = {
        'iat': int((issued_at - timedelta(seconds=30)).timestamp()),
        'exp': int((issued_at + timedelta(minutes=9)).timestamp()),
        'iss': github_app_id(),
    }
    return jwt.encode(payload, github_app_private_key(), algorithm='RS256')


async def mint_github_app_installation_token(
    *,
    installation_id: str,
    owner: Optional[str] = None,
    repo: Optional[str] = None,
    permissions: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    headers = {
        'Authorization': f'Bearer {build_github_app_jwt()}',
        'Accept': 'application/vnd.github+json',
        'User-Agent': 'codetether-github-app',
        'X-GitHub-Api-Version': '2022-11-28',
    }
    body: Dict[str, Any] = {}
    if repo:
        body['repositories'] = [repo]
    if permissions:
        body['permissions'] = permissions
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f'{github_api_base_url()}/app/installations/{installation_id}/access_tokens',
            headers=headers,
            json=body or None,
        )
        response.raise_for_status()
        return response.json()


async def github_installation_request(
    *,
    installation_id: str,
    method: str,
    url: str,
    owner: Optional[str] = None,
    repo: Optional[str] = None,
    json_body: Optional[Dict[str, Any]] = None,
) -> httpx.Response:
    token = await mint_github_app_installation_token(
        installation_id=installation_id,
        owner=owner,
        repo=repo,
    )
    headers = {
        'Authorization': f'Bearer {token["token"]}',
        'Accept': 'application/vnd.github+json',
        'User-Agent': 'codetether-github-app',
        'X-GitHub-Api-Version': '2022-11-28',
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.request(method, url, headers=headers, json=json_body)
        response.raise_for_status()
        return response
