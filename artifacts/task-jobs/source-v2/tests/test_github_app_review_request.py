import pytest

from a2a_server.github_app.review_request import (
    is_human_reviewer_login,
    request_human_review,
)


def test_is_human_reviewer_login_filters_app_and_bots():
    assert is_human_reviewer_login('rileyseaburg') is True
    assert is_human_reviewer_login('codetether[bot]') is False
    assert is_human_reviewer_login('codetether') is False
    assert is_human_reviewer_login('codetether-bot') is False
    assert is_human_reviewer_login('codetether-human') is True
    assert is_human_reviewer_login('dependabot[bot]') is False
    assert is_human_reviewer_login('') is False


@pytest.mark.asyncio
async def test_request_human_review_posts_requested_reviewers(monkeypatch):
    calls = []

    async def fake_github_json(method, path, token, payload=None):
        calls.append((method, path, token, payload))
        return {}

    monkeypatch.setattr(
        'a2a_server.github_app.review_request.github_json', fake_github_json
    )

    result = await request_human_review(
        'acme/widgets', 77, 'ghs_token', 'rileyseaburg'
    )

    assert result is True
    assert calls == [
        (
            'POST',
            '/repos/acme/widgets/pulls/77/requested_reviewers',
            'ghs_token',
            {'reviewers': ['rileyseaburg']},
        )
    ]


@pytest.mark.asyncio
async def test_request_human_review_skips_bot_login(monkeypatch):
    calls = []

    async def fake_github_json(method, path, token, payload=None):
        calls.append((method, path, token, payload))
        return {}

    monkeypatch.setattr(
        'a2a_server.github_app.review_request.github_json', fake_github_json
    )

    result = await request_human_review(
        'acme/widgets', 77, 'ghs_token', 'codetether[bot]'
    )

    assert result is False
    assert calls == []
