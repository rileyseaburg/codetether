"""Real PostgreSQL snapshot immutability, with the disposable runner fixture."""
# ruff: noqa: F811

import asyncio

from pathlib import Path

import pytest

from test_forgejo_automation_safety import writer_db  # noqa: F401

from a2a_server.forgejo_review_owner import state


@pytest.mark.asyncio
async def test_snapshot_is_immutable_and_separate_from_task_metadata(writer_db):  # noqa: F811
    migration = Path(
        'a2a_server/migrations/037_forgejo_review_snapshots.sql'
    ).read_text()
    async with writer_db.acquire() as conn:
        await conn.execute('ALTER TABLE tasks ADD PRIMARY KEY(id)')
        await conn.execute(migration)
        await conn.execute(
            "INSERT INTO tasks(id,status,agent_type,metadata) VALUES('owner','working','review_aggregate','{}'::jsonb)"
        )
    await state.save_snapshot(
        'owner', {'sha': 'original'}, [{'text': 'exact original diff'}]
    )
    await state.save_snapshot(
        'owner', {'sha': 'replacement'}, [{'text': 'wrong replacement'}]
    )
    saved = await state.snapshot('owner')
    assert saved == {
        'context': {'sha': 'original'},
        'chunks': [{'text': 'exact original diff'}],
    }
    async with writer_db.acquire() as conn:
        metadata = await conn.fetchval(
            "SELECT metadata::text FROM tasks WHERE id='owner'"
        )
    assert 'exact original diff' not in metadata


@pytest.mark.asyncio
async def test_concurrent_enrollment_creates_only_one_aggregate(
    writer_db,
    monkeypatch,  # noqa: F811
):
    monkeypatch.setenv('FORGEJO_API_URL', 'https://forge.example/api/v1')
    async with writer_db.acquire() as conn:
        await conn.execute('ALTER TABLE tasks ADD PRIMARY KEY(id)')
        await conn.execute("""ALTER TABLE tasks ADD COLUMN workspace_id TEXT,
            ADD COLUMN title TEXT,ADD COLUMN prompt TEXT,ADD COLUMN priority INTEGER,
            ADD COLUMN worker_id TEXT,ADD COLUMN result TEXT,ADD COLUMN error TEXT,
            ADD COLUMN updated_at TIMESTAMPTZ,ADD COLUMN started_at TIMESTAMPTZ,
            ADD COLUMN completed_at TIMESTAMPTZ,ADD COLUMN tenant_id TEXT""")
    pr = {'number': 7, 'head': {'sha': 'head', 'ref': 'branch'}}
    await asyncio.gather(
        *(
            state.ensure_record('owner/repo', pr, 'owner', 'workflow')
            for _ in range(6)
        )
    )
    async with writer_db.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT count(*) count, max(status) status FROM tasks WHERE id='owner'"
        )
    assert row['count'] == 1
    assert row['status'] == 'working'