"""Rudder runtime incident -> GitHub issue broker.

This endpoint lets an in-cluster Rudder controller send sanitized Kubernetes
runtime incidents to CodeTether. CodeTether owns the GitHub App private key,
mints a short-lived installation token, and creates or updates GitHub issues.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import quote

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from ..worker_auth import verify_auth
from .auth import github_json, installation_token

rudder_incident_router = APIRouter(
    prefix="/v1/integrations/rudder",
    tags=["rudder-incidents"],
)


class RudderIncidentPolicy(BaseModel):
    auto_create: bool = Field(default=False)
    update_existing: bool = Field(default=True)


class RudderIncidentRequest(BaseModel):
    repo: str = Field(..., description="GitHub repository in owner/name form")
    installation_id: int = Field(..., description="GitHub App installation id")
    fingerprint: str
    severity: str = Field(default="error")
    namespace: str
    release: Optional[str] = None
    workload: Optional[str] = None
    pod: Optional[str] = None
    container: Optional[str] = None
    reason: Optional[str] = None
    message: str
    log_excerpt: Optional[str] = None
    labels: list[str] = Field(default_factory=list)
    policy: RudderIncidentPolicy = Field(default_factory=RudderIncidentPolicy)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _issue_title(incident: RudderIncidentRequest) -> str:
    scope = incident.release or incident.workload or incident.namespace
    reason = incident.reason or incident.severity
    return f"[{incident.severity.upper()}] {scope}: {reason}"[:240]


def _issue_body(incident: RudderIncidentRequest) -> str:
    labels = ", ".join(incident.labels) if incident.labels else "none"
    excerpt = (incident.log_excerpt or incident.message).strip()[:12000]
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


async def _find_existing_issue(repo: str, fingerprint: str, token: str) -> Optional[dict[str, Any]]:
    query = quote(f'repo:{repo} is:issue is:open "rudder-log-fingerprint: {fingerprint}"')
    result = await github_json("GET", f"/search/issues?q={query}", token)
    items = result.get("items") or []
    return items[0] if items else None


@rudder_incident_router.post("/log-incidents")
async def reconcile_log_incident(request: Request, incident: RudderIncidentRequest) -> dict[str, Any]:
    """Create or update a GitHub issue for a sanitized Rudder LogIncident.

    Authentication uses the existing worker auth helper. If A2A_AUTH_TOKENS is
    configured, callers must send Authorization: Bearer <token>. The GitHub
    write itself uses a short-lived GitHub App installation token.
    """
    verify_auth(request)

    token, expires_at = await installation_token(incident.installation_id)
    existing = await _find_existing_issue(incident.repo, incident.fingerprint, token)
    body = _issue_body(incident)

    if existing and incident.policy.update_existing:
        issue_number = int(existing["number"])
        await github_json(
            "POST",
            f"/repos/{incident.repo}/issues/{issue_number}/comments",
            token,
            {"body": body[:65000]},
        )
        return {
            "action": "updated_existing_issue",
            "issue_number": issue_number,
            "issue_url": existing.get("html_url"),
            "token_expires_at": expires_at,
        }

    if not incident.policy.auto_create:
        return {
            "action": "drafted",
            "title": _issue_title(incident),
            "body": body,
            "existing_issue_url": existing.get("html_url") if existing else None,
            "token_expires_at": expires_at,
        }

    labels = sorted(set(["rudder", "k8s-log-error", *incident.labels]))
    created = await github_json(
        "POST",
        f"/repos/{incident.repo}/issues",
        token,
        {"title": _issue_title(incident), "body": body[:65000], "labels": labels},
    )
    return {
        "action": "created_issue",
        "issue_number": created.get("number"),
        "issue_url": created.get("html_url"),
        "token_expires_at": expires_at,
    }
