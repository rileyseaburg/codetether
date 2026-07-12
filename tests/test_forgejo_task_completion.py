# ruff: noqa: I001

import os

import a2a_server
import pytest

os.environ.setdefault(
    'DATABASE_URL', 'postgresql://test:test@localhost:5432/test'
)

from a2a_server import forgejo_task_completion
from a2a_server.github_app import task_status_hook


def task(status='completed'):
    return {
        'id': 'task-1',
        'status': status,
        'result': 'Pushed commit abc123.',
        'metadata': {
            'source': 'forgejo-webhook',
            'workflow_stage': 'code',
            'repo': 'riley/example',
            'issue_number': 42,
            'pr_number': 42,
            'forgejo_api_url': 'https://forgejo.example/api/v1',
        },
    }


@pytest.mark.asyncio
async def test_posts_completed_forgejo_terminal_comment(monkeypatch):
    calls = []

    async def fake_json(method, base, path, payload=None):
        calls.append((method, base, path, payload))
        return [] if method == 'GET' else {'id': 7}

    monkeypatch.setattr(forgejo_task_completion, 'forgejo_json', fake_json)
    await forgejo_task_completion.notify_forgejo_task_completion(task())

    assert [call[0] for call in calls] == ['GET', 'POST']
    body = calls[1][3]['body']
    assert 'Completed and pushed' in body
    assert 'Pushed commit abc123.' in body
    assert '<!-- codetether-forgejo-terminal:task-1 -->' in body


@pytest.mark.asyncio
async def test_skips_duplicate_forgejo_terminal_comment(monkeypatch):
    calls = []

    async def fake_json(method, base, path, payload=None):
        calls.append(method)
        return [{'body': '<!-- codetether-forgejo-terminal:task-1 -->'}]

    monkeypatch.setattr(forgejo_task_completion, 'forgejo_json', fake_json)
    await forgejo_task_completion.notify_forgejo_task_completion(task())
    assert calls == ['GET']


@pytest.mark.asyncio
async def test_terminal_hook_routes_forgejo_task(monkeypatch):
    seen = []

    async def fake_get(task_id):
        assert task_id == 'task-1'
        return task()

    async def fake_notify(value):
        seen.append(value)

    from a2a_server import database  # noqa: PLC0415

    monkeypatch.setattr(database, 'db_get_task', fake_get)
    monkeypatch.setattr(
        forgejo_task_completion, 'notify_forgejo_task_completion', fake_notify
    )
    await task_status_hook.handle_github_app_terminal_task('task-1')
    assert seen == [task()]
    delattr(a2a_server, 'database')
