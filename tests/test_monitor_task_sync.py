# ruff: noqa
from __future__ import annotations

from dataclasses import dataclass
import os

os.environ.setdefault(
    'DATABASE_URL', 'postgresql://user:pass@localhost:5432/test'
)

import pytest
from fastapi import HTTPException

from a2a_server import monitor_api


@dataclass
class FakeTask:
    id: str
    status: str
    result: str | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'status': self.status,
            'result': self.result,
            'error': self.error,
        }


class FakeBridge:
    def __init__(self, task: FakeTask):
        self.task = task

    async def get_task(self, task_id: str) -> FakeTask:
        assert task_id == self.task.id
        return self.task


@pytest.mark.asyncio
async def test_create_global_task_sync_returns_streamed_output(monkeypatch):
    async def fake_create_global_task(task_data):
        assert task_data.title == 'CodeTether PR Review'
        return {'id': 'task-review-1'}

    task = FakeTask(
        id='task-review-1',
        status='completed',
        result='APPROVED\n\nReviewed by CodeTether Agent.',
    )
    monitor_api._task_output_streams['task-review-1'] = [
        {'worker_id': 'wrk-1', 'output': 'Checking diff...', 'timestamp': 't1'},
        {'worker_id': 'wrk-1', 'output': 'APPROVED', 'timestamp': 't2'},
    ]
    monkeypatch.setattr(
        monitor_api, 'create_global_task', fake_create_global_task
    )
    monkeypatch.setattr(
        monitor_api, 'get_agent_bridge', lambda: FakeBridge(task)
    )

    response = await monitor_api.create_global_task_sync(
        monitor_api.AgentTaskCreateSync(
            title='CodeTether PR Review',
            prompt='Review this PR synchronously',
            timeout_seconds=1,
            poll_interval_seconds=0.1,
        )
    )

    assert response['success'] is True
    assert response['status'] == 'completed'
    assert response['result'] == 'APPROVED\n\nReviewed by CodeTether Agent.'
    assert [chunk['output'] for chunk in response['outputs']] == [
        'Checking diff...',
        'APPROVED',
    ]


@pytest.mark.asyncio
async def test_stream_task_run_events_emits_output_before_done(monkeypatch):
    task = FakeTask(
        id='task-review-stream',
        status='completed',
        result='CHANGES_REQUESTED',
    )
    monitor_api._task_output_streams['task-review-stream'] = [
        {
            'worker_id': 'wrk-1',
            'output': 'Reviewing changed files',
            'timestamp': 't1',
        },
    ]
    monkeypatch.setattr(
        monitor_api, 'get_agent_bridge', lambda: FakeBridge(task)
    )

    events = []
    async for line in monitor_api._stream_task_run_events(
        'task-review-stream',
        timeout_seconds=1,
        poll_interval_seconds=0.1,
    ):
        events.append(line)

    assert '"event": "task_started"' in events[0]
    assert '"event": "output"' in events[1]
    assert 'Reviewing changed files' in events[1]
    assert '"event": "done"' in events[2]
    assert 'CHANGES_REQUESTED' in events[2]


@pytest.mark.asyncio
async def test_create_global_task_sync_timeout_returns_504_with_partial_output(
    monkeypatch,
):
    async def fake_create_global_task(task_data):
        return {'id': 'task-review-2'}

    task = FakeTask(id='task-review-2', status='running')
    monitor_api._task_output_streams['task-review-2'] = [
        {
            'worker_id': 'wrk-1',
            'output': 'Still reviewing...',
            'timestamp': 't1',
        },
    ]
    monkeypatch.setattr(
        monitor_api, 'create_global_task', fake_create_global_task
    )
    monkeypatch.setattr(
        monitor_api, 'get_agent_bridge', lambda: FakeBridge(task)
    )

    with pytest.raises(HTTPException) as exc_info:
        await monitor_api.create_global_task_sync(
            monitor_api.AgentTaskCreateSync(
                title='CodeTether PR Review',
                prompt='Review this PR synchronously',
                timeout_seconds=0.01,
                poll_interval_seconds=0.1,
            )
        )

    assert exc_info.value.status_code == 504
    assert exc_info.value.detail['task_id'] == 'task-review-2'
    assert exc_info.value.detail['status'] == 'running'
    assert exc_info.value.detail['outputs'][0]['output'] == 'Still reviewing...'
