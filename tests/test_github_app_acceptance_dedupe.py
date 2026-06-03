import os

os.environ.setdefault(
    'DATABASE_URL', 'postgresql://test:test@localhost:5432/test'
)

import pytest

from a2a_server.github_app.watch import (
    ACCEPTED_COMMENT_FINGERPRINTS,
    _looks_like_acceptance_comment,
    _within_window,
    recent_app_acceptance_comment_exists,
)


def test_looks_like_acceptance_comment_matches_known_messages():
    body_pr = (
        '## 🛠️ CodeTether Fix\n\n'
        'Picked up this request for PR #614 on branch `codetether/issue-613`. '
        'I’m preparing the workspace and will push changes directly to the existing PR branch if the task succeeds. '
        'I will also make sure the branch is mergeable with `main`.'
    )
    body_issue = (
        '## 🛠️ CodeTether Fix\n\n'
        'Picked up issue #42 on branch `codetether/issue-42`. '
        'I’m preparing the workspace and will open a PR if the task succeeds.'
    )
    body_other = '## 🛠️ CodeTether Fix\n\nPushed changes to this PR branch.'
    assert _looks_like_acceptance_comment(body_pr) is True
    assert _looks_like_acceptance_comment(body_issue) is True
    assert _looks_like_acceptance_comment(body_other) is False
    assert _looks_like_acceptance_comment('') is False


def test_within_window_handles_z_suffix_and_recent_timestamps():
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    recent = (now - timedelta(seconds=30)).isoformat().replace('+00:00', 'Z')
    ancient = (now - timedelta(seconds=3600)).isoformat().replace('+00:00', 'Z')
    assert _within_window(recent, within_seconds=600) is True
    assert _within_window(ancient, within_seconds=600) is False
    assert _within_window('', within_seconds=600) is False
    assert _within_window('not-a-timestamp', within_seconds=600) is False


@pytest.mark.asyncio
async def test_recent_app_acceptance_comment_exists_true(monkeypatch):
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    recent = (now - timedelta(seconds=10)).isoformat().replace('+00:00', 'Z')

    async def fake_github_json(method, path, token, payload=None):
        return [
            {
                'user': {'login': 'codetether[bot]'},
                'body': '## 🛠️ CodeTether Fix\n\nPicked up this request for PR #614 on branch `x`.',
                'created_at': recent,
            }
        ]

    monkeypatch.setattr(
        'a2a_server.github_app.watch.github_json', fake_github_json
    )

    def fake_within(ts, within_seconds):
        assert ts == recent
        assert within_seconds == 600
        return True

    monkeypatch.setattr(
        'a2a_server.github_app.watch._within_window', fake_within
    )
    found = await recent_app_acceptance_comment_exists(
        'acme/widgets', 7, 'ghs_token', app_slug='codetether'
    )
    assert found is True


@pytest.mark.asyncio
async def test_recent_app_acceptance_comment_exists_false_for_human(monkeypatch):
    async def fake_github_json(method, path, token, payload=None):
        return [
            {
                'user': {'login': 'rileyseaburg'},
                'body': 'Picked up this request for PR #614 on branch `x`.',
                'created_at': '2024-01-01T00:00:00Z',
            }
        ]

    monkeypatch.setattr(
        'a2a_server.github_app.watch.github_json', fake_github_json
    )
    found = await recent_app_acceptance_comment_exists(
        'acme/widgets', 7, 'ghs_token', app_slug='codetether'
    )
    assert found is False
