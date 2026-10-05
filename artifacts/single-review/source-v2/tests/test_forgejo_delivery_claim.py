"""Duplicate webhook deliveries must not produce duplicate bot replies.

Forgejo delivered the same `comment.id` through both a repository hook and the
instance-wide system hook, ~80ms apart, so the bot posted "Picked this up"
twice on issue #4857.
"""

from __future__ import annotations

import pytest

from a2a_server import forgejo_delivery_claim as claim


def _ctx(comment_id: int = 0, number: int = 4857, repo: str = 'riley/spotlessbinco'):
    return {'repo': repo, 'number': number, 'comment_id': comment_id}


def test_comment_deliveries_share_one_key() -> None:
    first = claim.delivery_key('issue_comment', _ctx(comment_id=8737))
    second = claim.delivery_key('pull_request_comment', _ctx(comment_id=8737))

    assert first == second, (
        'the same comment delivered via two hooks must collapse to one key'
    )


def test_distinct_comments_get_distinct_keys() -> None:
    a = claim.delivery_key('issue_comment', _ctx(comment_id=8737))
    b = claim.delivery_key('issue_comment', _ctx(comment_id=8738))

    assert a != b, 'a genuinely new mention must not be suppressed'


def test_opened_issue_uses_a_body_key() -> None:
    key = claim.delivery_key('issues', _ctx(comment_id=0))

    assert key is not None
    assert key.endswith(':body'), key


def test_opened_issue_and_later_comment_are_separate() -> None:
    body = claim.delivery_key('issues', _ctx(comment_id=0))
    comment = claim.delivery_key('issue_comment', _ctx(comment_id=8737))

    assert body != comment


def test_different_repos_do_not_collide() -> None:
    a = claim.delivery_key('issue_comment', _ctx(comment_id=1, repo='riley/a'))
    b = claim.delivery_key('issue_comment', _ctx(comment_id=1, repo='riley/b'))

    assert a != b


@pytest.mark.parametrize(
    'ctx',
    [
        {'repo': '', 'number': 1, 'comment_id': 5},
        {'repo': 'riley/x', 'number': 0, 'comment_id': 5},
        {'repo': 'riley/x', 'comment_id': 5},
    ],
)
def test_unusable_context_yields_no_key(ctx: dict) -> None:
    assert claim.delivery_key('issue_comment', ctx) is None


def test_corrupt_comment_id_falls_back_to_body_key() -> None:
    key = claim.delivery_key(
        'issue_comment', {'repo': 'riley/x', 'number': 3, 'comment_id': 'nope'}
    )

    assert key is not None
    assert key.endswith(':body')


@pytest.mark.asyncio
async def test_first_delivery_wins_and_duplicate_loses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inserted: set[str] = set()

    class _Conn:
        async def execute(self, *args, **kwargs):
            return None

        async def fetchval(self, _sql, key, *args):
            if key in inserted:
                return None
            inserted.add(key)
            return key

    class _Acquire:
        async def __aenter__(self):
            return _Conn()

        async def __aexit__(self, *args):
            return None

    class _Pool:
        def acquire(self):
            return _Acquire()

    async def _pool():
        return _Pool()

    monkeypatch.setattr('a2a_server.database.get_pool', _pool, raising=False)

    ctx = _ctx(comment_id=8737)
    first, key = await claim.claim_delivery('issue_comment', ctx)
    second, same_key = await claim.claim_delivery('issue_comment', ctx)

    assert first is True, 'the first delivery must proceed'
    assert second is False, 'the duplicate delivery must be dropped'
    assert key == same_key


@pytest.mark.asyncio
async def test_storage_outage_does_not_silence_the_bot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _pool():
        raise RuntimeError('database unavailable')

    monkeypatch.setattr('a2a_server.database.get_pool', _pool, raising=False)

    claimed, _ = await claim.claim_delivery('issue_comment', _ctx(comment_id=1))

    assert claimed is True, (
        'a claim-store outage must not stop real work from being handled'
    )
