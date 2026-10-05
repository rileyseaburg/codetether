"""Mentions in a newly opened issue body must be handled.

Issue #4820 was filed with `@codetether handle this issue` in the body and the
bot never responded. Forgejo delivers that as `issues`/`opened`, but the webhook
only built a context for `issue_comment`, so the mention was dropped.
"""

from __future__ import annotations

import pytest

pytest.importorskip('fastapi')

from a2a_server import forgejo_webhooks as fw  # noqa: E402

REPO = {'full_name': 'riley/spotlessbinco', 'html_url': 'https://forgejo.example/riley/spotlessbinco'}


def _opened(body: str, *, author: str = 'riley', number: int = 4820) -> dict:
    return {
        'action': 'opened',
        'issue': {
            'number': number,
            'body': body,
            'html_url': f'https://forgejo.example/riley/spotlessbinco/issues/{number}',
            'user': {'login': author},
        },
        'repository': REPO,
        'sender': {'login': author},
    }


def test_issue_body_mention_is_handled() -> None:
    ctx = fw._context('issues', _opened('@codetether handle this issue'))

    assert ctx is not None, 'a mention in the issue body must be actionable'
    assert ctx['repo'] == 'riley/spotlessbinco'
    assert ctx['number'] == 4820
    assert ctx['is_pr'] is False
    assert ctx['comment_id'] == 0, 'no comment exists yet for an opened issue'
    assert ctx['actor_login'] == 'riley'


def test_bot_alias_in_issue_body_is_handled() -> None:
    ctx = fw._context('issues', _opened('@codetether-bot handle this issue'))

    assert ctx is not None
    assert ctx['number'] == 4820


def test_issue_body_without_mention_is_ignored() -> None:
    assert fw._context('issues', _opened('the LEADS API is broken')) is None


def test_non_opened_issue_actions_are_ignored() -> None:
    payload = _opened('@codetether handle this issue')
    payload['action'] = 'labeled'

    assert fw._context('issues', payload) is None


def test_comment_mentions_still_work() -> None:
    payload = {
        'action': 'created',
        'comment': {'id': 991, 'body': '@codetether handle this', 'user': {'login': 'riley'}},
        'issue': {'number': 4818, 'html_url': 'https://forgejo.example/i/4818'},
        'repository': REPO,
        'sender': {'login': 'riley'},
    }

    ctx = fw._context('issue_comment', payload)

    assert ctx is not None
    assert ctx['comment_id'] == 991
    assert ctx['number'] == 4818


def test_bot_authored_issue_is_self_authored() -> None:
    payload = _opened('@codetether handle this', author='codetether-bot')

    assert fw._is_self_authored(payload, 'issues') is True


def test_human_comment_on_bot_issue_is_not_self_authored() -> None:
    payload = {
        'action': 'created',
        'comment': {'id': 5, 'body': '@codetether handle this', 'user': {'login': 'riley'}},
        'issue': {'number': 10, 'user': {'login': 'codetether-bot'}},
        'repository': REPO,
        'sender': {'login': 'riley'},
    }

    assert fw._is_self_authored(payload, 'issue_comment') is False, (
        'the bot owns some repos; human comments there are real requests'
    )


def test_bot_comment_is_self_authored() -> None:
    payload = {
        'action': 'created',
        'comment': {'id': 6, 'body': 'progress update', 'user': {'login': 'codetether-bot'}},
        'issue': {'number': 10, 'user': {'login': 'riley'}},
        'repository': REPO,
        'sender': {'login': 'codetether-bot'},
    }

    assert fw._is_self_authored(payload, 'issue_comment') is True
