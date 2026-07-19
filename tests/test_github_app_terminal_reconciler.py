import os

os.environ.setdefault(
    'DATABASE_URL', 'postgresql://test:test@localhost:5432/test'
)

import pytest

from a2a_server import database as db
from a2a_server.github_app import task_completion, task_status_hook


class _FakeConnection:
    def __init__(self, rows):
        self.rows = rows
        self.query = ''
        self.limit = None

    async def fetch(self, query, limit):
        self.query = query
        self.limit = limit
        return self.rows


class _AcquireContext:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class _FakePool:
    def __init__(self, connection):
        self.connection = connection

    def acquire(self):
        return _AcquireContext(self.connection)


@pytest.mark.asyncio
async def test_reconciler_recovers_merge_and_fix_review_outcomes(monkeypatch):
    connection = _FakeConnection(
        [
            {'id': 'review-approved'},
            {'id': 'review-changes'},
            {'id': 'review-blocked'},
            {'id': 'review-without-verdict'},
        ]
    )
    pool = _FakePool(connection)
    tasks = {
        'review-approved': {
            'id': 'review-approved',
            'result': 'APPROVED: looks safe',
        },
        'review-changes': {
            'id': 'review-changes',
            'result': 'CHANGES_REQUESTED: fix the tests',
        },
        'review-blocked': {
            'id': 'review-blocked',
            'result': 'BLOCKED: provenance mismatch',
        },
        'review-without-verdict': {
            'id': 'review-without-verdict',
            'result': 'review completed',
        },
    }
    handled = []

    async def fake_get_pool():
        return pool

    async def fake_get_task(task_id):
        return tasks[task_id]

    async def fake_notify(task, worker_id=None):
        handled.append(task['id'])

    monkeypatch.setattr(db, 'get_pool', fake_get_pool)
    monkeypatch.setattr(db, 'db_get_task', fake_get_task)
    monkeypatch.setattr(
        task_completion, 'notify_issue_task_completion', fake_notify
    )

    count = await task_status_hook.reconcile_github_app_terminal_tasks(limit=9)

    assert count == 3
    assert handled == [
        'review-approved',
        'review-changes',
        'review-blocked',
    ]
    assert connection.limit == 9
    assert "d.action = 'github:merge_pr'" in connection.query
    assert "fix.metadata->>'review_task_id' = t.id" in connection.query
    assert "fix.metadata->>'fix_followup' = 'true'" in connection.query
    assert "t.result ILIKE '%CHANGES_REQUESTED%'" in connection.query
    assert "t.result ~* 'BLOCKED\\s*:'" in connection.query


@pytest.mark.asyncio
async def test_reconciler_returns_zero_without_database_pool(monkeypatch):
    async def fake_get_pool():
        return None

    monkeypatch.setattr(db, 'get_pool', fake_get_pool)

    assert await task_status_hook.reconcile_github_app_terminal_tasks() == 0
