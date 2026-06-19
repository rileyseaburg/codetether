"""Rudder runtime incident -> GitHub issue broker.

This endpoint lets an in-cluster Rudder controller send sanitized Kubernetes
runtime incidents to CodeTether. CodeTether owns the GitHub App private key,
mints a short-lived installation token, and creates or updates GitHub issues.
"""

from __future__ import annotations

import hashlib
import re
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

_ASSIGNMENT_ID_RE = re.compile(
    r"(?i)\b("
    r"advertiser|advertiser_id|customer|customer_id|campaign|campaign_id|"
    r"adgroup|adgroup_id|ad_group|ad_group_id|account|account_id|task|"
    r"task_id|request|request_id|trace|trace_id|span|span_id|run|run_id|"
    r"job|job_id|execution|execution_id"
    r")\s*(=|:)\s*['\"]?[\w./:-]+['\"]?"
)
_NOUN_ID_RE = re.compile(
    r"(?i)\b("
    r"advertiser|customer|campaign|adgroup|ad group|account|task|request|"
    r"trace|span|run|job|execution"
    r")\s+[\w.-]*\d{6,}[\w.-]*\b"
)
_UUID_RE = re.compile(
    r"(?i)\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"
)
_LONG_HEX_RE = re.compile(r"(?i)\b[0-9a-f]{16,}\b")
_LONG_NUMBER_RE = re.compile(r"\b\d{6,}\b")
_WHITESPACE_RE = re.compile(r"\s+")


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


def _normalize_incident_text(value: str | None) -> str:
    """Collapse volatile ids while keeping the useful error shape."""
    text = (value or "").strip().lower()
    if not text:
        return ""
    text = _UUID_RE.sub("<uuid>", text)
    text = _ASSIGNMENT_ID_RE.sub(lambda match: f"{match.group(1).lower()}=<id>", text)
    text = _NOUN_ID_RE.sub(lambda match: f"{match.group(1).lower()} <id>", text)
    text = _LONG_HEX_RE.sub("<hex>", text)
    text = _LONG_NUMBER_RE.sub("<num>", text)
    return _WHITESPACE_RE.sub(" ", text).strip()


def _incident_group_fingerprint(incident: RudderIncidentRequest) -> str:
    identity = [
        incident.severity.lower().strip(),
        incident.namespace.lower().strip(),
        (incident.release or "").lower().strip(),
        (incident.workload or "").lower().strip(),
        (incident.container or "").lower().strip(),
        (incident.reason or "").lower().strip(),
        _normalize_incident_text(incident.message),
        _normalize_incident_text(incident.log_excerpt),
    ]
    digest = hashlib.sha256("\n".join(identity).encode("utf-8")).hexdigest()[:16]
    return f"sha256:{digest}"


def _stable_message_phrase(incident: RudderIncidentRequest) -> str:
    text = (incident.message or incident.log_excerpt or "").strip()
    if ":" in text:
        text = text.rsplit(":", 1)[-1]
    text = re.sub(r"\([^)]*\)", " ", text)
    text = _ASSIGNMENT_ID_RE.sub(" ", text)
    text = _NOUN_ID_RE.sub(" ", text)
    text = _UUID_RE.sub(" ", text)
    text = _LONG_HEX_RE.sub(" ", text)
    text = _LONG_NUMBER_RE.sub(" ", text)
    text = _WHITESPACE_RE.sub(" ", text).strip(" -:;,.")
    return text[:120]


def _issue_body(incident: RudderIncidentRequest) -> str:
    labels = ", ".join(incident.labels) if incident.labels else "none"
    excerpt = (incident.log_excerpt or incident.message).strip()[:12000]
    group_fingerprint = _incident_group_fingerprint(incident)
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

## Dedupe fingerprints

`rudder-log-group: {group_fingerprint}`

`rudder-log-fingerprint: {incident.fingerprint}`

<!-- rudder-log-group: {group_fingerprint} -->
<!-- rudder-log-fingerprint: {incident.fingerprint} -->
"""


async def _search_first_issue(query: str, token: str) -> Optional[dict[str, Any]]:
    result = await github_json(
        "GET",
        f"/search/issues?q={quote(query)}&sort=updated&order=desc",
        token,
    )
    items = result.get("items") or []
    return items[0] if items else None


async def _find_existing_issue(
    repo: str, incident: RudderIncidentRequest, token: str
) -> Optional[dict[str, Any]]:
    exact = await _search_first_issue(
        f'repo:{repo} is:issue is:open "rudder-log-fingerprint: {incident.fingerprint}"',
        token,
    )
    if exact:
        return exact

    group_fingerprint = _incident_group_fingerprint(incident)
    grouped = await _search_first_issue(
        f'repo:{repo} is:issue is:open "rudder-log-group: {group_fingerprint}"',
        token,
    )
    if grouped:
        return grouped

    phrase = _stable_message_phrase(incident)
    if len(phrase) >= 12:
        fallback = await _search_first_issue(
            f'repo:{repo} is:issue is:open in:title "{_issue_title(incident)}" '
            f'label:rudder label:k8s-log-error "{phrase}"',
            token,
        )
        if fallback:
            return fallback

    return await _search_first_issue(
        f'repo:{repo} is:issue is:open in:title "{_issue_title(incident)}" '
        'label:rudder label:k8s-log-error',
        token,
    )


@rudder_incident_router.post("/log-incidents")
async def reconcile_log_incident(request: Request, incident: RudderIncidentRequest) -> dict[str, Any]:
    """Create or update a GitHub issue for a sanitized Rudder LogIncident.

    Authentication uses the existing worker auth helper. If A2A_AUTH_TOKENS is
    configured, callers must send Authorization: Bearer <token>. The GitHub
    write itself uses a short-lived GitHub App installation token.
    """
    verify_auth(request)

    token, expires_at = await installation_token(incident.installation_id)
    group_fingerprint = _incident_group_fingerprint(incident)
    existing = await _find_existing_issue(incident.repo, incident, token)
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
            "dedupe_group": group_fingerprint,
            "token_expires_at": expires_at,
        }

    if not incident.policy.auto_create:
        return {
            "action": "drafted",
            "title": _issue_title(incident),
            "body": body,
            "existing_issue_url": existing.get("html_url") if existing else None,
            "dedupe_group": group_fingerprint,
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
        "dedupe_group": group_fingerprint,
        "token_expires_at": expires_at,
    }
