"""Real PostgreSQL intake/locking tests with explicitly mocked provider effects.

Run with FORGEJO_INBOX_TEST_DSN pointing only at a disposable test database.
Each test owns a distinct schema, retained for inspecting failed evidence.
"""
# ruff: noqa: PLR2004, PLC0415, E501, SLF001

import asyncio
import json
import os
import uuid

from unittest.mock import AsyncMock

import asyncpg
import pytest
import pytest_asyncio

from a2a_server import database
from a2a_server import forgejo_inbox as inbox
from a2a_server import forgejo_inbox_dispatch as effects
from a2a_server import forgejo_inbox_worker as pump


DSN = os.getenv('FORGEJO_INBOX_TEST_DSN')
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not DSN, reason='disposable PostgreSQL required'),
]
BASE = 'https://forge.example/api/v1'
CONTEXT = {
    'repo': 'owner/repo',
    'number': 5863,
    'is_pr': False,
    'body': '@codetether handle this issue',
    'comment_id': 0,
    'repo_data': {},
    'actor_login': 'owner',
    'html_url': '',
}


@pytest_asyncio.fixture
async def db(monkeypatch):
    schema = 'inbox_test_' + uuid.uuid4().hex
    conn = await asyncpg.connect(DSN)
    await conn.execute(f'CREATE SCHEMA {schema}')
    await conn.close()
    pool = await asyncpg.create_pool(
        DSN, min_size=1, max_size=8, server_settings={'search_path': schema}
    )
    monkeypatch.setattr(database, 'get_pool', AsyncMock(return_value=pool))
    async with pool.acquire() as conn:
        await conn.execute(
            'CREATE TABLE tasks (id TEXT, status TEXT, metadata JSONB)'
        )
    yield pool
    await pool.close()


@pytest.fixture
def provider(monkeypatch):
    plan = {
        'branch': 'main',
        'head_sha': '',
        'default_branch': 'main',
        'repo_data': {},
    }
    prepare = AsyncMock(return_value=plan)
    dispatch = AsyncMock(
        return_value={'accepted': True, 'forgejo_agent_task_id': 42}
    )
    ack = AsyncMock()
    monkeypatch.setattr(effects, 'prepare_plan', prepare)
    monkeypatch.setattr(effects, 'dispatch', dispatch)
    monkeypatch.setattr(effects, 'acknowledge', ack)
    return prepare, dispatch, ack


async def stored(db, identity):
    async with db.acquire() as conn:
        return await conn.fetchrow(
            'SELECT * FROM forgejo_webhook_inbox WHERE delivery_id = $1',
            identity,
        )


async def due_now(db, identity):
    async with db.acquire() as conn:
        await conn.execute(
            'UPDATE forgejo_webhook_inbox SET next_attempt_at = now() WHERE delivery_id = $1',
            identity,
        )


async def test_concurrent_receipts_commit_one_immutable_payload(db):
    receipts = await asyncio.gather(
        *(inbox.accept('issues', CONTEXT, BASE) for _ in range(16))
    )
    identity = receipts[0]['delivery_id']
    assert {r['delivery_id'] for r in receipts} == {identity}
    duplicate = await inbox.accept(
        'issue', {**CONTEXT, 'body': 'changed'}, BASE
    )
    assert duplicate['delivery_id'] == identity
    row = await stored(db, identity)
    assert inbox.decode(row['context'])['body'] == CONTEXT['body']
    assert row['state'] == 'pending'


async def test_independent_comment_is_not_silenced_by_old_claim(db):
    async with db.acquire() as conn:
        from a2a_server.forgejo_delivery_claim import ensure_table

        await ensure_table(conn)
        await conn.execute(
            "INSERT INTO forgejo_webhook_deliveries (delivery_key,repo,issue_number,event) VALUES ('owner/repo#5863:issues:body','owner/repo',5863,'issues')"
        )
    body = await inbox.accept('issues', CONTEXT, BASE)
    comment = await inbox.accept(
        'issue_comment', {**CONTEXT, 'comment_id': 17}, BASE
    )
    assert body['delivery_id'] != comment['delivery_id']
    assert body['state'] == comment['state'] == 'pending'


async def test_failure_retries_without_any_new_webhook_and_reuses_plan(
    db, provider
):
    prepare, dispatch, ack = provider
    dispatch.side_effect = [
        RuntimeError('vault unavailable'),
        {'accepted': True},
    ]
    identity = (await inbox.accept('issues', CONTEXT, BASE))['delivery_id']
    await pump.reconcile()
    row = await stored(db, identity)
    assert row['state'] == 'pending'
    assert row['error_code'] == 'RuntimeError'
    assert row['attempts'] == 1
    assert row['receipt_notified']
    await due_now(db, identity)
    await pump.reconcile()
    assert (await stored(db, identity))['state'] == 'acknowledged'
    prepare.assert_awaited_once()
    assert dispatch.await_count == 2
    assert ack.await_count == 2


async def test_ack_failure_keeps_handoff_checkpoint_and_never_redispatches(
    db, provider
):
    _, dispatch, ack = provider
    ack.side_effect = [None, RuntimeError('lost response'), None]
    identity = (await inbox.accept('issues', CONTEXT, BASE))['delivery_id']
    await pump.process(identity)
    assert (await stored(db, identity))['state'] == 'dispatched'
    await due_now(db, identity)
    await pump.process(identity)
    dispatch.assert_awaited_once()
    assert (await stored(db, identity))['state'] == 'acknowledged'


async def test_concurrent_workers_serialize_distinct_comments_for_same_issue(
    db,
):
    first = (await inbox.accept('issues', CONTEXT, BASE))['delivery_id']
    second = (
        await inbox.accept('issue_comment', {**CONTEXT, 'comment_id': 2}, BASE)
    )['delivery_id']
    async with inbox.locked_delivery(first) as owner:
        assert owner is not None
        async with inbox.locked_delivery(second) as other:
            assert other is None
    async with inbox.locked_delivery(second) as successor:
        assert successor is not None


async def test_prior_native_workflow_blocks_next_mention_until_terminal(
    db, provider, monkeypatch
):
    identity = (await inbox.accept('issues', CONTEXT, BASE))['delivery_id']
    await pump.process(identity)
    async with db.acquire() as conn:
        await conn.execute(
            'UPDATE forgejo_webhook_inbox SET native_task_id=42 WHERE delivery_id=$1',
            identity,
        )
    second = (
        await inbox.accept('issue_comment', {**CONTEXT, 'comment_id': 2}, BASE)
    )['delivery_id']
    native = AsyncMock(return_value={'status': 'accepted'})
    monkeypatch.setattr('a2a_server.forgejo_agent_client.get_task', native)
    await pump.process(second)
    assert (await stored(db, second))['state'] == 'pending'
    assert provider[1].await_count == 1
    native.return_value = {'status': 'completed'}
    await due_now(db, second)
    await pump.process(second)
    assert (await stored(db, second))['state'] == 'acknowledged'
    assert provider[1].await_count == 2


async def test_connection_death_releases_lock_without_releasing_receipt(db):
    identity = (await inbox.accept('issues', CONTEXT, BASE))['delivery_id']
    # A killed PostgreSQL backend models process/socket death, not graceful
    # exception cleanup: no release_delivery or advisory unlock is executed.
    conn = await db.acquire()
    lock = f'forgejo-inbox:{BASE}:owner/repo:5863'
    await conn.execute('SELECT pg_advisory_lock(hashtextextended($1,0))', lock)
    pid = conn.get_server_pid()
    terminated = asyncio.Event()
    conn.add_termination_listener(lambda closed: terminated.set())
    async with db.acquire() as other:
        assert await other.fetchval('SELECT pg_terminate_backend($1)', pid)
    await asyncio.wait_for(terminated.wait(), timeout=5)
    await db.release(conn)
    async with inbox.locked_delivery(identity) as replacement:
        assert replacement is not None
    assert (await stored(db, identity))['state'] == 'pending'


async def test_cancelled_dispatch_stays_retryable(db, provider):
    provider[1].side_effect = asyncio.CancelledError()
    identity = (await inbox.accept('issues', CONTEXT, BASE))['delivery_id']
    with pytest.raises(asyncio.CancelledError):
        await pump.process(identity)
    row = await stored(db, identity)
    assert row['state'] == 'pending'
    assert row['error_code'] == 'CancelledError'
    async with inbox.locked_delivery(identity) as replacement:
        assert replacement is not None


async def test_ack_marker_reconciles_response_loss_and_pagination(monkeypatch):
    from a2a_server import forgejo_webhooks as hooks

    marker = '<!-- codetether-inbox:delivery -->'
    get = AsyncMock(
        side_effect=[
            [{'body': 'other'}] * 100,
            [{'body': marker, 'user': {'login': 'codetether'}}],
        ]
    )
    post = AsyncMock()
    monkeypatch.setattr(hooks, 'forgejo_json', get)
    monkeypatch.setattr(hooks, '_comment', post)
    await effects.acknowledge('delivery', CONTEXT, BASE, {'accepted': True})
    assert get.await_count == 2
    post.assert_not_awaited()
    get.side_effect = None
    get.return_value = [{'body': marker, 'user': {'login': 'unrelated-user'}}]
    await effects.acknowledge('delivery', CONTEXT, BASE, {'accepted': True})
    post.assert_awaited_once()


async def test_recovery_is_dry_run_by_default_and_idempotent_when_requested(
    db, monkeypatch
):
    from a2a_server import forgejo_inbox_recovery as recovery
    from a2a_server.forgejo_delivery_claim import ensure_table

    key = 'owner/repo#5863:issues:body'
    monkeypatch.setenv('FORGEJO_API_URL', BASE)
    async with db.acquire() as conn:
        await ensure_table(conn)
        await conn.execute(
            """
            INSERT INTO forgejo_webhook_deliveries
                (delivery_key,repo,issue_number,event) VALUES ($1,'owner/repo',5863,'issues')
        """,
            key,
        )

    async def provider_get(method, base, path):
        assert method == 'GET'
        if '/agent/tasks?' in path:
            return {'tasks': []}
        if path.endswith('/issues/5863'):
            return {
                'number': 5863,
                'body': CONTEXT['body'],
                'state': 'open',
                'user': {'login': 'owner'},
            }
        assert path == '/repos/owner/repo'
        return {'full_name': 'owner/repo'}

    monkeypatch.setattr(recovery.hooks, 'forgejo_json', provider_get)
    planned = await recovery.recover(key)
    assert planned['eligible'] and 'receipt' not in planned
    async with db.acquire() as conn:
        assert (
            await conn.fetchval("SELECT to_regclass('forgejo_webhook_inbox')")
            is None
        )
    first = await recovery.recover(key, enqueue=True)
    second = await recovery.recover(key, enqueue=True)
    assert first['receipt']['delivery_id'] == second['receipt']['delivery_id']
    async with db.acquire() as conn:
        assert (
            await conn.fetchval('SELECT count(*) FROM forgejo_webhook_inbox')
            == 1
        )
        assert (
            await conn.fetchval(
                'SELECT count(*) FROM forgejo_webhook_deliveries'
            )
            == 1
        )
        await conn.execute(
            "INSERT INTO tasks VALUES ('existing','completed',$1::jsonb)",
            json.dumps(
                {
                    'source': 'forgejo-webhook',
                    'repo': 'owner/repo',
                    'issue_number': 5863,
                }
            ),
        )
    refused = await recovery.recover(key, enqueue=True)
    assert refused['reason'] == 'existing-work'


async def test_temporal_replay_does_not_restart_terminal_workflow(monkeypatch):
    from types import SimpleNamespace

    from temporalio.common import WorkflowIDReusePolicy
    from temporalio.exceptions import WorkflowAlreadyStartedError

    from a2a_server.temporal import client

    temporal = AsyncMock()
    temporal.start_workflow.side_effect = WorkflowAlreadyStartedError(
        'forgejo-agent-task-42', 'ForgejoAgentWorkflow'
    )
    monkeypatch.setattr(
        client, 'get_temporal_client', AsyncMock(return_value=temporal)
    )
    result = await client.start_forgejo_workflow(
        SimpleNamespace(forgejo_task_id=42)
    )
    assert result == 'forgejo-agent-task-42'
    assert (
        temporal.start_workflow.call_args.kwargs['id_reuse_policy']
        == WorkflowIDReusePolicy.REJECT_DUPLICATE
    )


async def test_reported_still_not_working_is_an_actionable_retry():
    from a2a_server.github_app.mention import is_fix_request

    assert is_fix_request('@codetether still not working')
    assert not is_fix_request('still not working')


async def test_intake_fails_closed_when_database_unavailable(monkeypatch):
    from fastapi import HTTPException

    monkeypatch.setattr(database, 'get_pool', AsyncMock(return_value=None))
    with pytest.raises(HTTPException) as failure:
        await inbox.accept('issues', CONTEXT, BASE)
    assert failure.value.status_code == 503


async def test_raw_webhook_secrets_do_not_enter_receipt(db):
    secret = 'sensitive-sentinel-not-for-inbox'
    ctx = {
        **CONTEXT,
        'headers': {'Authorization': secret},
        'repo_data': {'token': secret},
    }
    identity = (await inbox.accept('issues', ctx, BASE))['delivery_id']
    assert secret not in str((await stored(db, identity))['context'])


async def test_native_retry_cannot_resume_over_successor_receipt(
    db, monkeypatch
):
    from fastapi import HTTPException

    first = (await inbox.accept('issues', CONTEXT, BASE))['delivery_id']
    await effects.bind_native(first, 42)
    async with inbox.execution_ownership(
        'owner/repo', 5863, 42, BASE, attempt=2
    ):
        pass
    await inbox.accept('issue_comment', {**CONTEXT, 'comment_id': 20}, BASE)
    with pytest.raises(HTTPException) as refused:
        async with inbox.execution_ownership(
            'owner/repo', 5863, 42, BASE, attempt=2
        ):
            raise AssertionError('superseded retry must not execute')
    assert refused.value.status_code == 409
    from a2a_server.temporal import client
    from a2a_server.temporal.models import ForgejoControlSignal

    handle = AsyncMock()
    monkeypatch.setattr(
        client, 'workflow_handle', AsyncMock(return_value=handle)
    )
    with pytest.raises(HTTPException):
        await client.signal_control(
            ForgejoControlSignal(action='retry', forgejo_task_id=42)
        )
    handle.signal.assert_not_awaited()
    await client.signal_control(
        ForgejoControlSignal(action='cancel', forgejo_task_id=42)
    )
    handle.signal.assert_awaited_once()
    # Followup comments do not abort ordinary stages of the initial attempt.
    async with (
        inbox.execution_ownership('owner/repo', 5863, 42, BASE, attempt=1),
        inbox.locked_delivery(first) as contender,
    ):
        assert contender is None


async def test_nonactionable_comment_does_not_supersede_native_retry(db):
    first = (await inbox.accept('issues', CONTEXT, BASE))['delivery_id']
    await effects.bind_native(first, 42)
    await inbox.accept(
        'issue_comment',
        {**CONTEXT, 'comment_id': 21, 'body': '@codetether hello'},
        BASE,
    )
    async with inbox.execution_ownership(
        'owner/repo', 5863, 42, BASE, attempt=2
    ):
        pass


async def test_temporal_requires_configured_base_before_provider_mutations(
    monkeypatch,
):
    from fastapi import HTTPException

    from a2a_server import forgejo_webhooks as hooks

    monkeypatch.setenv('FORGEJO_TEMPORAL_ENABLED', 'true')
    monkeypatch.delenv('FORGEJO_API_URL', raising=False)
    call = AsyncMock()
    monkeypatch.setattr(hooks, 'forgejo_json', call)
    with pytest.raises(HTTPException) as refused:
        await hooks._dispatch(CONTEXT, BASE)
    assert refused.value.status_code == 503
    call.assert_not_awaited()


async def test_signed_http_request_commits_before_disconnected_worker_runs(
    db, provider, monkeypatch
):
    import hashlib
    import hmac

    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient

    from a2a_server import forgejo_webhooks as hooks

    monkeypatch.setenv('FORGEJO_WEBHOOK_SECRET', 'local-test-secret')
    monkeypatch.setenv('FORGEJO_API_URL', BASE)
    app = FastAPI()
    app.include_router(hooks.forgejo_webhook_router)
    raw = json.dumps(
        {
            'action': 'opened',
            'issue': {
                'number': 5863,
                'body': CONTEXT['body'],
                'user': {'login': 'owner'},
            },
            'repository': {'full_name': CONTEXT['repo']},
        }
    ).encode()
    headers = {
        'X-Forgejo-Event': 'issues',
        'X-Forgejo-Signature': hmac.new(
            b'local-test-secret', raw, hashlib.sha256
        ).hexdigest(),
    }
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url='http://test'
    ) as client:
        response = await client.post(
            '/v1/webhooks/forgejo', content=raw, headers=headers
        )
    assert response.status_code == 200
    identity = response.json()['delivery_id']
    assert (await stored(db, identity))['state'] == 'pending'
    provider[1].assert_not_awaited()
    # A later, independently invoked worker uses only the committed receipt.
    await pump.reconcile()
    assert (await stored(db, identity))['state'] == 'acknowledged'
    provider[1].assert_awaited_once()


async def test_temporal_legacy_lookup_and_activity_fence_use_real_postgres(
    db, monkeypatch
):
    from a2a_server.temporal import activities
    from a2a_server.temporal.models import (
        ForgejoAgentWorkflowInput,
        ForgejoStageRequest,
    )

    monkeypatch.setenv('FORGEJO_API_URL', BASE)
    identity = (await inbox.accept('issues', CONTEXT, BASE))['delivery_id']
    await effects.bind_native(identity, 42)
    workflow = ForgejoAgentWorkflowInput(
        forgejo_task_id=42,
        repository='owner/repo',
        issue_number=5863,
        pull_request_number=0,
        workspace_id='workspace-1',
        branch='main',
        head_sha='before',
        operation='fix',
    )
    request = ForgejoStageRequest(
        workflow=workflow, workflow_id='workflow-42', stage='prepare'
    )
    meta = activities._temporal_metadata(
        request, branch='main', head_sha='after', pull_request_number=0
    )
    new_key = meta['forgejo_work_key']
    meta['forgejo_work_key'] = 'forgejo-temporal:42:1:prepare:before'
    async with db.acquire() as conn:
        await conn.execute(
            "INSERT INTO tasks VALUES ('legacy','completed',$1::jsonb)",
            json.dumps(meta),
        )
        await conn.execute(
            "INSERT INTO tasks VALUES ('new-key','completed',$1::jsonb)",
            json.dumps({**meta, 'forgejo_work_key': new_key}),
        )
    async with activities._execution_ownership(request):
        async with inbox.locked_delivery(identity) as blocked:
            assert blocked is None
        assert await activities._legacy_stage_task_id(request) == 'legacy'
    # Ambiguous old-stage history must never be turned into a fresh worker.
    async with db.acquire() as conn:
        await conn.execute(
            "INSERT INTO tasks VALUES ('legacy-duplicate','completed',$1::jsonb)",
            json.dumps(
                {
                    **meta,
                    'forgejo_work_key': 'forgejo-temporal:42:1:prepare:another',
                }
            ),
        )
    with pytest.raises(RuntimeError, match='Ambiguous legacy'):
        await activities._legacy_stage_task_id(request)


async def test_router_lifespan_runs_pump_even_without_configured_base(
    monkeypatch,
):
    from fastapi import FastAPI

    from a2a_server import forgejo_webhooks as hooks

    monkeypatch.delenv('FORGEJO_API_URL', raising=False)
    starts = []
    stop = AsyncMock()
    monkeypatch.setattr(pump, 'start', lambda: starts.append(True))
    monkeypatch.setattr(pump, 'stop', stop)
    app = FastAPI()
    app.include_router(hooks.forgejo_webhook_router)
    async with app.router.lifespan_context(app):
        assert starts == [True]
        stop.assert_not_awaited()
    stop.assert_awaited_once()
