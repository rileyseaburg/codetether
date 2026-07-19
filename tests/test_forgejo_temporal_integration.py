from __future__ import annotations

from types import SimpleNamespace

import pytest
from temporalio.exceptions import ApplicationError

from a2a_server import forgejo_task_completion
from a2a_server import forgejo_webhooks
from a2a_server.temporal import activities
from a2a_server.temporal.activities import safe_activity
from a2a_server.temporal.models import ForgejoAgentWorkflowInput


@pytest.mark.asyncio
async def test_activity_failure_does_not_persist_sensitive_exception_text():
    @safe_activity('safe_failure_code')
    async def fail():
        raise RuntimeError('authorization=must-not-leak')

    with pytest.raises(ApplicationError) as error:
        await fail()
    assert error.value.type == 'safe_failure_code'
    assert error.value.message == 'safe_failure_code'
    assert 'must-not-leak' not in str(error.value)


@pytest.mark.asyncio
async def test_temporal_dispatch_starts_workflow_without_legacy_clone(
    monkeypatch,
):
    started: list[ForgejoAgentWorkflowInput] = []
    updates: list[dict] = []

    async def fake_json(method, base, path, payload=None):
        if path.endswith('/pulls/12'):
            return {'head': {'ref': 'feature', 'sha': 'abc123'}}
        return {
            'default_branch': 'main',
            'clone_url': 'https://forge.example/owner/repo.git',
        }

    async def fake_workspace(ctx, clone_url, branch, token):
        assert 'token' not in ctx
        return 'workspace-1'

    async def fake_create_agent_task(**kwargs):
        assert 'must-not-leak' not in str(kwargs.get('metadata'))
        return {
            'id': 42,
            'html_url': 'https://forge.example/owner/repo/agent/tasks/42',
        }

    async def fake_start(workflow_input):
        started.append(workflow_input)
        return 'forgejo-agent-task-42'

    async def fake_update(**kwargs):
        updates.append(kwargs)
        return {'id': 42}

    async def fail_legacy_dispatch(**kwargs):
        raise AssertionError(
            'legacy clone dispatch must not run in Temporal mode'
        )

    monkeypatch.setattr(forgejo_webhooks, 'forgejo_json', fake_json)
    monkeypatch.setattr(forgejo_webhooks, '_ensure_workspace', fake_workspace)
    monkeypatch.setattr(forgejo_webhooks, '_token', lambda: 'secret-token')
    monkeypatch.setattr(
        forgejo_webhooks, 'resolve_task_target', lambda: _async_value({})
    )
    monkeypatch.setattr(
        'a2a_server.forgejo_agent_client.create_task', fake_create_agent_task
    )
    monkeypatch.setattr(
        'a2a_server.forgejo_agent_client.update_task', fake_update
    )
    monkeypatch.setattr(
        'a2a_server.temporal.config.temporal_settings',
        lambda: SimpleNamespace(enabled=True),
    )
    monkeypatch.setattr(
        'a2a_server.temporal.client.start_forgejo_workflow', fake_start
    )
    monkeypatch.setattr(
        'a2a_server.persistent_worker_pool.create_and_dispatch_task',
        fail_legacy_dispatch,
    )

    result = await forgejo_webhooks._dispatch(
        {
            'repo': 'owner/repo',
            'number': 12,
            'is_pr': True,
            'body': '@codetether fix this',
            'html_url': 'https://forge.example/owner/repo/pulls/12',
            'actor_login': 'alice',
            'comment_id': 9,
        },
        'https://forge.example/api/v1',
    )

    assert result['temporal_workflow_id'] == 'forgejo-agent-task-42'
    assert len(started) == 1
    assert started[0] == ForgejoAgentWorkflowInput(
        forgejo_task_id=42,
        repository='owner/repo',
        issue_number=12,
        pull_request_number=12,
        workspace_id='workspace-1',
        branch='feature',
        head_sha='abc123',
        operation='fix',
    )
    assert updates[-1]['status'] == 'accepted'


@pytest.mark.asyncio
async def test_finalize_handles_non_list_comment_response(monkeypatch):
    updates = []
    comments = []

    async def fake_update(**kwargs):
        updates.append(kwargs)
        return {'id': 42}

    async def fake_json(*args, **kwargs):
        return {'user_error': 'unexpected response'}

    async def fake_comment(*args):
        comments.append(args)

    monkeypatch.setenv('FORGEJO_API_URL', 'https://forge.example/api/v1')
    monkeypatch.setattr(
        'a2a_server.forgejo_agent_client.update_task', fake_update
    )
    monkeypatch.setattr(forgejo_webhooks, 'forgejo_json', fake_json)
    monkeypatch.setattr(forgejo_webhooks, '_comment', fake_comment)

    await activities.finalize_workflow(
        {
            'repository': 'owner/repo',
            'forgejo_task_id': 42,
            'status': 'completed',
            'active_task_id': 'task-1',
            'issue_number': 7,
            'attempt': 1,
        }
    )

    assert updates == [
        {
            'repo': 'owner/repo',
            'task_id': 42,
            'status': 'completed',
            'external_task_id': 'task-1',
        }
    ]
    assert len(comments) == 1
    assert '<!-- codetether-temporal:42:1 -->' in comments[0][3]


async def _async_value(value):
    return value


@pytest.mark.asyncio
async def test_temporal_terminal_sync_signals_without_legacy_followup(
    monkeypatch,
):
    sync_calls = []
    signals = []

    async def fake_sync(task, *, workflow_terminal=True):
        sync_calls.append((task, workflow_terminal))

    async def fake_signal(forgejo_task_id, signal):
        signals.append((forgejo_task_id, signal))

    async def fail_legacy(*args, **kwargs):
        raise AssertionError('legacy stage advancement must not run')

    monkeypatch.setattr(
        forgejo_task_completion, 'sync_forgejo_agent_task', fake_sync
    )
    monkeypatch.setattr(
        'a2a_server.temporal.client.signal_task_terminal', fake_signal
    )
    monkeypatch.setattr(
        forgejo_task_completion, 'create_forgejo_review_task', fail_legacy
    )
    monkeypatch.setattr(
        forgejo_task_completion, 'create_forgejo_fix_followup', fail_legacy
    )

    task = {
        'id': 'review-1',
        'status': 'completed',
        'session_id': 'session-1',
        'result': 'APPROVED: focused tests pass',
        'metadata': {
            'source': 'forgejo-webhook',
            'workflow_stage': 'review',
            'temporal_orchestrated': True,
            'forgejo_agent_task_id': 42,
            'repo': 'owner/repo',
            'pr_number': 12,
            'pr_head_sha': 'abc123',
        },
    }
    await forgejo_task_completion.notify_forgejo_task_completion(task)

    assert sync_calls == [(task, False)]
    assert len(signals) == 1
    forgejo_task_id, signal = signals[0]
    assert forgejo_task_id == 42
    assert signal.task_id == 'review-1'
    assert signal.stage == 'review'
    assert signal.status == 'completed'
    assert signal.verdict == 'APPROVED'
