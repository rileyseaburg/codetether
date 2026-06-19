from urllib.parse import parse_qs, urlparse

import pytest

from a2a_server.github_app import rudder_incidents
from a2a_server.github_app.rudder_incidents import RudderIncidentRequest


def _incident(message: str, fingerprint: str = "sha256:raw") -> RudderIncidentRequest:
    return RudderIncidentRequest(
        repo="owner/repo",
        installation_id=123,
        fingerprint=fingerprint,
        severity="error",
        namespace="production",
        release="spotlessbinco",
        workload="spotlessbinco-api",
        pod="spotlessbinco-api-123",
        container="api",
        reason="LogErrorPattern",
        message=message,
        log_excerpt=message,
        labels=["production", "spotlessbinco"],
    )


def test_rudder_group_fingerprint_ignores_volatile_ids():
    first = _incident(
        "[tiktok-async-report] Failed for advertiser 7426011654007128082: "
        "Timed out waiting for TikTok download_url (task_id=7648847897416761352)",
        "sha256:first",
    )
    second = _incident(
        "[tiktok-async-report] Failed for advertiser 7500239282796576785: "
        "Timed out waiting for TikTok download_url (task_id=7648848098168422408)",
        "sha256:second",
    )

    assert (
        rudder_incidents._incident_group_fingerprint(first)
        == rudder_incidents._incident_group_fingerprint(second)
    )


def test_rudder_group_fingerprint_keeps_error_shape():
    timeout = _incident(
        "[tiktok-async-report] Failed for advertiser 7426011654007128082: "
        "Timed out waiting for TikTok download_url (task_id=7648847897416761352)"
    )
    auth = _incident(
        "[tiktok-async-report] Failed for advertiser 7426011654007128082: "
        "TikTok API returned 401 Unauthorized (task_id=7648847897416761352)"
    )

    assert (
        rudder_incidents._incident_group_fingerprint(timeout)
        != rudder_incidents._incident_group_fingerprint(auth)
    )


def test_rudder_issue_body_includes_exact_and_group_markers():
    incident = _incident(
        "[tiktok-async-report] Failed for advertiser 7426011654007128082: "
        "Timed out waiting for TikTok download_url (task_id=7648847897416761352)",
        "sha256:raw-fingerprint",
    )

    body = rudder_incidents._issue_body(incident)

    assert "rudder-log-group: sha256:" in body
    assert "rudder-log-fingerprint: sha256:raw-fingerprint" in body


@pytest.mark.asyncio
async def test_rudder_existing_issue_search_falls_back_to_stable_phrase(monkeypatch):
    incident = _incident(
        "[tiktok-async-report] Failed for advertiser 7426011654007128082: "
        "Timed out waiting for TikTok download_url (task_id=7648847897416761352)",
        "sha256:raw-fingerprint",
    )
    calls: list[str] = []

    async def fake_github_json(method, path, token, payload=None):
        calls.append(path)
        query = parse_qs(urlparse(path).query).get("q", [""])[0]
        if "rudder-log-fingerprint:" in query:
            return {"items": []}
        if "rudder-log-group:" in query:
            return {"items": []}
        if "Timed out waiting for TikTok download_url" in query:
            return {"items": [{"number": 42, "html_url": "https://example.test/42"}]}
        return {"items": []}

    monkeypatch.setattr(rudder_incidents, "github_json", fake_github_json)

    existing = await rudder_incidents._find_existing_issue(
        "owner/repo", incident, "token"
    )

    assert existing == {"number": 42, "html_url": "https://example.test/42"}
    assert len(calls) == 3
