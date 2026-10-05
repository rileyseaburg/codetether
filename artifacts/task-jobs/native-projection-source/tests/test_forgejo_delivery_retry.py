"""Mocked-local coverage for retrying a claimed but undispatched mention."""
# ruff: noqa: SLF001, PLC0415

import asyncio

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from fastapi import HTTPException

from a2a_server import database
from a2a_server import forgejo_delivery_claim as claims
from a2a_server import forgejo_webhooks as webhook


@pytest.mark.asyncio
async def test_cleanup_failure_retains_owned_claim(monkeypatch):
    """A pruning failure after insertion must not lose ownership tracking."""
    key = 'owner/repo#5863:issues:body'
    conn = AsyncMock()
    conn.fetchval.return_value = key
    conn.execute.side_effect = [None, RuntimeError('pruning unavailable')]
    pool = MagicMock()
    pool.acquire.return_value.__aenter__.return_value = conn
    monkeypatch.setattr(database, 'get_pool', AsyncMock(return_value=pool))

    acquired, owned = await claims.claim_delivery(
        'issues', {'repo': 'owner/repo', 'number': 5863}
    )
    assert acquired is True
    assert owned == key


@pytest.mark.asyncio
async def test_storage_failure_does_not_own_another_claim(monkeypatch):
    monkeypatch.setattr(
        database, 'get_pool', AsyncMock(side_effect=RuntimeError('offline'))
    )
    acquired, owned = await claims.claim_delivery(
        'issues', {'repo': 'owner/repo', 'number': 5863}
    )
    assert acquired is True
    assert owned is None


@pytest.fixture
def delivery_store(monkeypatch):
    """Use the real claim/release SQL call sites with an in-memory store."""
    keys = set()

    class Connection:
        async def execute(self, sql, *args):
            if 'WHERE delivery_key = $1' in sql:
                keys.discard(args[0])

        async def fetchval(self, sql, key, *args):
            if key in keys:
                return None
            keys.add(key)
            return key

    class Pool:
        @asynccontextmanager
        async def acquire(self):
            yield Connection()

    monkeypatch.setattr(database, 'get_pool', AsyncMock(return_value=Pool()))
    return keys


@pytest.fixture
def webhook_request(monkeypatch):
    """Model an authenticated issue-open webhook without external effects."""
    payload = {
        'action': 'opened',
        'issue': {'number': 5863, 'body': '@codetether handle this issue'},
        'repository': {'full_name': 'owner/repo'},
        'sender': {'login': 'owner'},
    }
    monkeypatch.setattr(webhook, 'verify_forgejo_signature', lambda *a: None)
    monkeypatch.setattr(
        webhook, '_api_base', lambda *a: 'https://forge.example/api/v1'
    )
    monkeypatch.setattr(webhook, '_active_task', AsyncMock(return_value=False))
    monkeypatch.setattr(webhook, '_comment', AsyncMock())
    req = AsyncMock()
    req.headers = {'X-Forgejo-Event': 'issues'}
    req.body.return_value = b'{}'
    req.json.return_value = payload
    return req


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'failure',
    [
        HTTPException(503, 'Credential storage unavailable'),
        asyncio.CancelledError(),
    ],
)
async def test_storage_failure_is_not_acknowledged(
    monkeypatch, delivery_store, webhook_request, failure
):
    from a2a_server import forgejo_inbox

    accept = AsyncMock(side_effect=failure)
    monkeypatch.setattr(forgejo_inbox, 'accept', accept)
    dispatch = AsyncMock()
    monkeypatch.setattr(webhook, '_dispatch', dispatch)

    with pytest.raises(type(failure)) as caught:
        await webhook.handle_forgejo_webhook(webhook_request)
    assert caught.value is failure
    dispatch.assert_not_awaited()
    webhook._comment.assert_not_awaited()


@pytest.mark.asyncio
async def test_receipt_precedes_all_external_effects(
    monkeypatch, delivery_store, webhook_request
):
    from a2a_server import forgejo_inbox

    receipt = {
        'accepted': True,
        'delivery_id': 'durable-id',
        'state': 'pending',
    }
    accept = AsyncMock(return_value=receipt)
    monkeypatch.setattr(forgejo_inbox, 'accept', accept)
    dispatch = AsyncMock()
    monkeypatch.setattr(webhook, '_dispatch', dispatch)

    result = await webhook.handle_forgejo_webhook(webhook_request)
    assert result == receipt
    accept.assert_awaited_once()
    dispatch.assert_not_awaited()
    webhook._comment.assert_not_awaited()


@pytest.mark.asyncio
async def test_fail_open_has_no_claim_ownership(monkeypatch):
    monkeypatch.setattr(database, 'get_pool', AsyncMock(return_value=None))
    acquired, key = await claims.claim_delivery(
        'issues', {'repo': 'o/r', 'number': 1}
    )
    assert acquired is True
    assert key is None
    database.get_pool.reset_mock()
    await claims.release_delivery(key)
    database.get_pool.assert_not_awaited()


@pytest.mark.asyncio
async def test_release_failure_preserves_dispatch_error(
    monkeypatch, webhook_request
):
    monkeypatch.setattr(
        claims, 'claim_delivery', AsyncMock(return_value=(True, 'owned-key'))
    )
    monkeypatch.setattr(
        database,
        'get_pool',
        AsyncMock(side_effect=RuntimeError('database unavailable')),
    )
    failure = HTTPException(503, 'Credential storage unavailable')
    from a2a_server import forgejo_inbox

    monkeypatch.setattr(forgejo_inbox, 'accept', AsyncMock(side_effect=failure))
    with pytest.raises(HTTPException) as caught:
        await webhook.handle_forgejo_webhook(webhook_request)
    assert caught.value is failure
