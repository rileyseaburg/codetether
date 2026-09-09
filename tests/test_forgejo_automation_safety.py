"""Containment, single-writer admission, and no unsolicited status edits."""
# ruff: noqa: PLC0415, PLR2004, E501, SLF001

import asyncio
import json
import os
import uuid

from unittest.mock import AsyncMock

import asyncpg
import pytest
import pytest_asyncio

from fastapi import HTTPException

from a2a_server import database
from a2a_server import forgejo_automation as automation
from a2a_server.forgejo_automation_policy import (
    pr_is_paused,
    status_remediation_enabled,
)
from a2a_server.forgejo_writer_guard import single_writer


@pytest.mark.asyncio
async def test_readonly_chunks_do_not_take_writer_slots_but_builds_still_do(
    writer_db, monkeypatch
):
    monkeypatch.setenv('FORGEJO_REVIEW_SAFE_WORKER', 'safe-reviewer')
    readonly = {
        'source': 'forgejo-webhook',
        'repo': 'owner/repo',
        'pr_number': 7,
        'workflow_stage': 'review_chunk',
        'agent_type': 'plan',
        'target_agent_name': 'safe-reviewer',
        'required_capabilities': ['review-readonly'],
    }
    async with writer_db.acquire() as conn:
        await conn.execute(
            "INSERT INTO tasks(id,status,agent_type,metadata) VALUES('reader','running','plan',$1::jsonb)",
            json.dumps(readonly),
        )
    writer = {
        'source': 'forgejo-webhook',
        'repo': 'owner/repo',
        'pr_number': 7,
        'agent_type': 'build',
        'forgejo_work_key': 'repair',
    }
    async with single_writer(writer):
        async with writer_db.acquire() as conn:
            await conn.execute(
                "INSERT INTO tasks(id,status,agent_type,metadata) VALUES('writer','running','build',$1::jsonb)",
                json.dumps(writer),
            )
    with pytest.raises(HTTPException):
        async with single_writer({**writer, 'forgejo_work_key': 'another'}):
            pytest.fail('parallel writer admitted')


def test_status_edits_require_explicit_opt_in(monkeypatch):
    monkeypatch.delenv('FORGEJO_STATUS_REMEDIATION_ENABLED', raising=False)
    assert not status_remediation_enabled()
    monkeypatch.setenv('FORGEJO_STATUS_REMEDIATION_ENABLED', 'true')
    assert status_remediation_enabled()


def test_pause_matches_only_named_request(monkeypatch):
    monkeypatch.setenv(
        'FORGEJO_AUTOMATION_PAUSED_PRS', ' riley/spotlessbinco#5873 '
    )
    assert pr_is_paused('riley/spotlessbinco', 5873)
    assert not pr_is_paused('riley/spotlessbinco', 5870)
    assert not pr_is_paused('riley/other', 5873)


@pytest.mark.parametrize(
    'context',
    [
        'CodeTether PR Review / CodeTether Review (pull_request_target)',
        'codetether/review',
        'CodeTether Review',
    ],
)
def test_bot_does_not_repair_its_own_review_gate(context):
    assert automation.is_self_status(
        {'context': context, 'creator': {'login': 'forgejo-actions'}}
    )


@pytest.mark.asyncio
async def test_disabled_status_path_does_no_discovery(monkeypatch):
    monkeypatch.delenv('FORGEJO_STATUS_REMEDIATION_ENABLED', raising=False)
    get_pool = AsyncMock(side_effect=AssertionError('must not scan tasks'))
    get = AsyncMock(side_effect=AssertionError('must not scan Forgejo'))
    monkeypatch.setattr(database, 'get_pool', get_pool)
    monkeypatch.setattr(automation, 'forgejo_json', get)
    assert await automation.reconcile_forgejo_failures() == 0
    assert (
        await automation.create_status_remediation_task(
            base='https://forge.example/api/v1',
            repo='owner/repo',
            pr={},
            status={'status': 'failure'},
        )
        is None
    )
    from a2a_server.forgejo_webhooks import _handle_status_event

    assert (await _handle_status_event({}, 'https://forge.example/api/v1'))[
        'reason'
    ] == 'status-remediation-disabled'
    get_pool.assert_not_awaited()
    get.assert_not_awaited()


@pytest.mark.asyncio
async def test_paused_writer_is_rejected_before_database(monkeypatch):
    monkeypatch.setenv('FORGEJO_AUTOMATION_PAUSED_PRS', 'owner/repo#5873')
    get_pool = AsyncMock(side_effect=AssertionError('must not touch storage'))
    monkeypatch.setattr(database, 'get_pool', get_pool)
    with pytest.raises(HTTPException) as error:
        async with single_writer(
            {
                'source': 'forgejo-webhook',
                'repo': 'owner/repo',
                'pr_number': 5873,
            }
        ):
            pytest.fail('paused writer admitted')
    assert error.value.status_code == 409
    from a2a_server.forgejo_inbox import accept

    with pytest.raises(HTTPException) as receipt:
        await accept(
            'issues',
            {'repo': 'owner/repo', 'number': 5873},
            'https://forge.example/api/v1',
        )
    assert receipt.value.status_code == 409
    get_pool.assert_not_awaited()


@pytest_asyncio.fixture
async def writer_db(monkeypatch):
    dsn = os.getenv('FORGEJO_INBOX_TEST_DSN')
    if not dsn:
        pytest.skip('disposable PostgreSQL required')
    schema = 'writer_test_' + uuid.uuid4().hex
    conn = await asyncpg.connect(dsn)
    await conn.execute(f'CREATE SCHEMA {schema}')
    await conn.close()
    pool = await asyncpg.create_pool(
        dsn, min_size=1, max_size=6, server_settings={'search_path': schema}
    )
    async with pool.acquire() as conn:
        await conn.execute(
            'CREATE TABLE tasks (id TEXT,status TEXT,agent_type TEXT,metadata JSONB,created_at TIMESTAMPTZ DEFAULT now())'
        )
    monkeypatch.setattr(database, 'get_pool', AsyncMock(return_value=pool))
    monkeypatch.delenv('FORGEJO_AUTOMATION_PAUSED_PRS', raising=False)
    yield pool
    await pool.close()


@pytest.mark.asyncio
async def test_different_checks_and_heads_cannot_spawn_parallel_writers(
    writer_db,
):
    base = {
        'source': 'forgejo-webhook',
        'repo': 'riley/spotlessbinco',
        'pr_number': 5873,
        'agent_type': 'build',
    }
    admitted = []

    async def create(key):
        metadata = {**base, 'forgejo_work_key': key}
        try:
            async with single_writer(metadata):
                async with writer_db.acquire() as conn:
                    await conn.execute(
                        "INSERT INTO tasks(id,status,agent_type,metadata) VALUES($1,'running','build',$2::jsonb)",
                        key,
                        json.dumps(metadata),
                    )
                admitted.append(key)
        except HTTPException as error:
            assert error.status_code == 409

    await asyncio.gather(
        create('old-head:wrapper'),
        create('old-head:child'),
        create('new-head:review'),
    )
    assert len(admitted) == 1
    # A retry of exactly the same immutable work may reuse the existing task.
    async with single_writer({**base, 'forgejo_work_key': admitted[0]}):
        pass
    async with writer_db.acquire() as conn:
        assert await conn.fetchval('SELECT count(*) FROM tasks') == 1
        await conn.execute("UPDATE tasks SET status='completed'")
    await create('later-head:tests')
    assert len(admitted) == 2
