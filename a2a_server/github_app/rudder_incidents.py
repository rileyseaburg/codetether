"""Rudder runtime incident -> issue broker.

This endpoint lets an in-cluster Rudder controller send sanitized Kubernetes
runtime incidents to CodeTether. New deployments publish incidents to Forgejo.
The legacy GitHub App path is retained only for repos that have not migrated.
"""

from __future__ import annotations

import os

from datetime import UTC, datetime
from typing import Literal
from urllib.parse import quote

import httpx

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from a2a_server.github_app.auth import github_json, installation_token
from a2a_server.worker_auth import verify_auth


HTTP_BAD_REQUEST = 400
ISSUE_BODY_LIMIT = 65000
ISSUE_TITLE_LIMIT = 240
LOG_EXCERPT_LIMIT = 12000
RECENT_ISSUE_LIMIT = 50

rudder_incident_router = APIRouter(
    prefix='/v1/integrations/rudder',
    tags=['rudder-incidents'],
)


class RudderIncidentPolicy(BaseModel):
    """Rudder incident publication behavior."""

    auto_create: bool = Field(default=False)
    update_existing: bool = Field(default=True)


class RudderIncidentRequest(BaseModel):
    """Sanitized Rudder incident payload."""

    repo: str = Field(..., description='Repository in owner/name form')
    provider: Literal['forgejo', 'github'] = Field(
        default='forgejo',
        description=(
            'Issue tracker provider. Forgejo is the migration target; '
            'GitHub is legacy.'
        ),
    )
    installation_id: int | None = Field(
        default=None,
        description=(
            'GitHub App installation id; required only when provider=github'
        ),
    )
    fingerprint: str
    severity: str = Field(default='error')
    namespace: str
    release: str | None = None
    workload: str | None = None
    pod: str | None = None
    container: str | None = None
    reason: str | None = None
    message: str
    log_excerpt: str | None = None
    labels: list[str] = Field(default_factory=list)
    policy: RudderIncidentPolicy = Field(default_factory=RudderIncidentPolicy)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _issue_title(incident: RudderIncidentRequest) -> str:
    scope = incident.release or incident.workload or incident.namespace
    reason = incident.reason or incident.severity
    title = f'[{incident.severity.upper()}] {scope}: {reason}'
    return title[:ISSUE_TITLE_LIMIT]


def _issue_body(incident: RudderIncidentRequest) -> str:
    labels = ', '.join(incident.labels) if incident.labels else 'none'
    excerpt = (incident.log_excerpt or incident.message).strip()
    excerpt = excerpt[:LOG_EXCERPT_LIMIT]
    return f"""## Rudder Kubernetes runtime incident

{incident.message}

## Scope

- Namespace: `{incident.namespace}`
- Release: `{incident.release or 'unknown'}`
- Workload: `{incident.workload or 'unknown'}`
- Pod: `{incident.pod or 'unknown'}`
- Container: `{incident.container or 'unknown'}`
- Severity: `{incident.severity}`
- Reason: `{incident.reason or 'unknown'}`
- Labels: `{labels}`
- Reported at: `{_now_iso()}`

## Evidence

```text
{excerpt}
```

## Dedupe fingerprint

`rudder-log-fingerprint: {incident.fingerprint}`

<!-- rudder-log-fingerprint: {incident.fingerprint} -->
"""


async def _find_existing_issue(
    repo: str,
    fingerprint: str,
    token: str,
) -> dict[str, object] | None:
    query = quote(
        f'repo:{repo} is:issue is:open "rudder-log-fingerprint: {fingerprint}"',
    )
    result = await github_json('GET', f'/search/issues?q={query}', token)
    items = result.get('items') or []
    return items[0] if items else None


def _forgejo_api_base_url() -> str:
    configured = (
        (
            os.environ.get('FORGEJO_API_BASE_URL')
            or os.environ.get('CODETETHER_FORGEJO_API_BASE_URL')
            or os.environ.get('FORGEJO_URL')
            or os.environ.get('CODETETHER_FORGEJO_URL')
            or ''
        )
        .strip()
        .rstrip('/')
    )
    if not configured:
        raise HTTPException(
            status_code=503,
            detail=(
                'Forgejo API base URL is not configured (FORGEJO_API_BASE_URL)'
            ),
        )
    if not configured.endswith('/api/v1'):
        configured = f'{configured}/api/v1'
    return configured


def _forgejo_token() -> str:
    token = (
        os.environ.get('FORGEJO_TOKEN')
        or os.environ.get('CODETETHER_FORGEJO_TOKEN')
        or os.environ.get('FORGEJO_API_TOKEN')
        or ''
    ).strip()
    if not token:
        raise HTTPException(
            status_code=503,
            detail='Forgejo token is not configured (FORGEJO_TOKEN)',
        )
    return token


async def forgejo_json(
    method: str,
    path: str,
    payload: dict[str, object] | None = None,
) -> dict[str, object] | list[dict[str, object]]:
    """Call the Forgejo/Gitea-compatible REST API."""
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.request(
            method,
            f'{_forgejo_api_base_url()}{path}',
            headers={
                'Accept': 'application/json',
                'Authorization': f'token {_forgejo_token()}',
                'User-Agent': 'codetether-rudder-forgejo',
            },
            json=payload,
        )
    if response.status_code >= HTTP_BAD_REQUEST:
        raise HTTPException(
            status_code=502,
            detail=f'Forgejo API {method} {path} failed: {response.text[:400]}',
        )
    parsed = response.json() if response.content else {}
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        return parsed
    return {}


async def _find_existing_forgejo_issue(
    repo: str,
    fingerprint: str,
) -> dict[str, object] | None:
    encoded_query = quote(f'rudder-log-fingerprint: {fingerprint}')
    items = await forgejo_json(
        'GET',
        f'/repos/{repo}/issues?state=open&q={encoded_query}',
    )
    if not isinstance(items, list):
        items = []
    for item in items:
        body = str((item or {}).get('body') or '')
        title = str((item or {}).get('title') or '')
        if fingerprint in body or fingerprint in title:
            return item
    if items:
        return items[0]

    recent = await forgejo_json(
        'GET',
        f'/repos/{repo}/issues?state=open&limit={RECENT_ISSUE_LIMIT}',
    )
    if not isinstance(recent, list):
        return None
    needle = f'rudder-log-fingerprint: {fingerprint}'
    for item in recent:
        if needle in str((item or {}).get('body') or ''):
            return item
    return None


def _issue_number(issue: dict[str, object]) -> int:
    return int(issue.get('number') or issue.get('index'))


def _issue_url(issue: dict[str, object]) -> object:
    return issue.get('html_url') or issue.get('url')


async def _reconcile_forgejo_incident(
    incident: RudderIncidentRequest,
) -> dict[str, object]:
    existing = await _find_existing_forgejo_issue(
        incident.repo,
        incident.fingerprint,
    )
    body = _issue_body(incident)

    if existing and incident.policy.update_existing:
        issue_number = _issue_number(existing)
        await forgejo_json(
            'POST',
            f'/repos/{incident.repo}/issues/{issue_number}/comments',
            {'body': body[:ISSUE_BODY_LIMIT]},
        )
        return {
            'provider': 'forgejo',
            'action': 'updated_existing_issue',
            'issue_number': issue_number,
            'issue_url': _issue_url(existing),
        }

    if not incident.policy.auto_create:
        return {
            'provider': 'forgejo',
            'action': 'drafted',
            'title': _issue_title(incident),
            'body': body,
            'existing_issue_url': _issue_url(existing) if existing else None,
        }

    created = await forgejo_json(
        'POST',
        f'/repos/{incident.repo}/issues',
        {'title': _issue_title(incident), 'body': body[:ISSUE_BODY_LIMIT]},
    )
    if not isinstance(created, dict):
        created = {}
    return {
        'provider': 'forgejo',
        'action': 'created_issue',
        'issue_number': created.get('number') or created.get('index'),
        'issue_url': _issue_url(created),
    }


@rudder_incident_router.post('/log-incidents')
async def reconcile_log_incident(
    request: Request,
    incident: RudderIncidentRequest,
) -> dict[str, object]:
    """Create or update an issue for a sanitized Rudder LogIncident.

    Authentication uses the existing worker auth helper. If A2A_AUTH_TOKENS is
    configured, callers must send Authorization: Bearer <token>. Forgejo writes
    use FORGEJO_TOKEN. Legacy GitHub writes use a short-lived GitHub App
    installation token.
    """
    verify_auth(request)

    if incident.provider == 'forgejo':
        return await _reconcile_forgejo_incident(incident)

    if incident.installation_id is None:
        raise HTTPException(
            status_code=422,
            detail='installation_id is required when provider=github',
        )

    token, expires_at = await installation_token(incident.installation_id)
    existing = await _find_existing_issue(
        incident.repo,
        incident.fingerprint,
        token,
    )
    body = _issue_body(incident)

    if existing and incident.policy.update_existing:
        issue_number = int(existing['number'])
        await github_json(
            'POST',
            f'/repos/{incident.repo}/issues/{issue_number}/comments',
            token,
            {'body': body[:ISSUE_BODY_LIMIT]},
        )
        return {
            'provider': 'github',
            'action': 'updated_existing_issue',
            'issue_number': issue_number,
            'issue_url': existing.get('html_url'),
            'token_expires_at': expires_at,
        }

    if not incident.policy.auto_create:
        return {
            'provider': 'github',
            'action': 'drafted',
            'title': _issue_title(incident),
            'body': body,
            'existing_issue_url': (
                existing.get('html_url') if existing else None
            ),
            'token_expires_at': expires_at,
        }

    labels = sorted({'rudder', 'k8s-log-error', *incident.labels})
    created = await github_json(
        'POST',
        f'/repos/{incident.repo}/issues',
        token,
        {
            'title': _issue_title(incident),
            'body': body[:ISSUE_BODY_LIMIT],
            'labels': labels,
        },
    )
    return {
        'provider': 'github',
        'action': 'created_issue',
        'issue_number': created.get('number'),
        'issue_url': created.get('html_url'),
        'token_expires_at': expires_at,
    }
