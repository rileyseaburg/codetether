from __future__ import annotations

import pytest

from a2a_server import forgejo_agent_client
from a2a_server import forgejo_task_completion as completion
from a2a_server import session_view


@pytest.mark.asyncio
async def test_sync_terminal_task_updates_forgejo_and_publishes_transcript(
    monkeypatch,
):
    updates: list[dict] = []
    publishes: list[dict] = []

    async def fake_messages(task, limit):
        assert limit == 10_000
        return 'session-9', [
            {
                'role': 'assistant',
                'content': 'Done',
                'tool_calls': [{'name': 'pytest', 'output': '2 passed'}],
            }
        ]

    async def fake_update(**kwargs):
        updates.append(kwargs)
        return {'id': kwargs['task_id']}

    async def fake_publish(**kwargs):
        publishes.append(kwargs)
        return 2

    monkeypatch.setattr(session_view, '_task_messages', fake_messages)
    monkeypatch.setattr(forgejo_agent_client, 'update_task', fake_update)
    monkeypatch.setattr(
        forgejo_agent_client, 'publish_session_events', fake_publish
    )

    task = {
        'id': 'codetether-77',
        'status': 'completed',
        'result': 'Implemented and tested',
        'error': '',
        'metadata': {
            'source': 'forgejo-webhook',
            'repo': 'acme/widgets',
            'forgejo_api_url': 'https://forgejo.example/api/v1',
            'forgejo_agent_task_id': 42,
            'forgejo_agent_task_url': (
                'https://forgejo.example/acme/widgets/agent/tasks/42'
            ),
            'pr_head_sha': 'abc123',
            'branch_name': 'codetether/issue-7',
        },
    }
    await completion.sync_forgejo_agent_task(task)

    assert updates == [
        {
            'repo': 'acme/widgets',
            'task_id': 42,
            'base_url': 'https://forgejo.example/api/v1',
            'status': 'completed',
            'external_task_id': 'codetether-77',
            'external_session_id': 'session-9',
            'head_sha': 'abc123',
            'branch': 'codetether/issue-7',
            'result': 'Implemented and tested',
            'error': '',
        }
    ]
    assert publishes == [
        {
            'repo': 'acme/widgets',
            'forgejo_task_id': 42,
            'codetether_task_id': 'codetether-77',
            'messages': [
                {
                    'role': 'assistant',
                    'content': 'Done',
                    'tool_calls': [{'name': 'pytest', 'output': '2 passed'}],
                }
            ],
            'base_url': 'https://forgejo.example/api/v1',
        }
    ]


@pytest.mark.asyncio
async def test_dispatch_creates_forgejo_task_before_codetether_and_links_it(
    monkeypatch,
):
    from a2a_server import forgejo_webhooks
    from a2a_server import persistent_worker_pool

    calls: list[tuple[str, dict]] = []

    async def fake_json(method, base, path, payload=None):
        assert method == 'GET'
        return {
            'default_branch': 'main',
            'clone_url': 'https://forgejo.example/acme/widgets.git',
        }

    async def fake_workspace(ctx, clone_url, branch, token):
        return 'workspace-1'

    async def fake_routing():
        return {'required_capabilities': ['persistent-workspace']}

    async def fake_create(**kwargs):
        calls.append(('forgejo-create', kwargs))
        return {
            'id': 42,
            'html_url': 'https://forgejo.example/acme/widgets/agent/tasks/42',
        }

    async def fake_dispatch(**kwargs):
        calls.append(('codetether-dispatch', kwargs))
        return 'codetether-77'

    async def fake_update(**kwargs):
        calls.append(('forgejo-update', kwargs))
        return {'id': 42}

    monkeypatch.setenv('FORGEJO_TOKEN', 'secret')
    monkeypatch.setattr(forgejo_webhooks, 'forgejo_json', fake_json)
    monkeypatch.setattr(forgejo_webhooks, '_ensure_workspace', fake_workspace)
    monkeypatch.setattr(forgejo_webhooks, 'resolve_task_target', fake_routing)
    monkeypatch.setattr(forgejo_agent_client, 'create_task', fake_create)
    monkeypatch.setattr(forgejo_agent_client, 'update_task', fake_update)
    monkeypatch.setattr(
        persistent_worker_pool, 'create_and_dispatch_task', fake_dispatch
    )

    result = await forgejo_webhooks._dispatch(
        {
            'repo': 'acme/widgets',
            'number': 7,
            'is_pr': False,
            'body': '@codetether fix this issue',
            'repo_data': {},
            'comment_id': 9,
            'html_url': 'https://forgejo.example/acme/widgets/issues/7',
            'actor_login': 'alice',
        },
        'https://forgejo.example/api/v1',
    )

    assert [name for name, _ in calls] == [
        'forgejo-create',
        'codetether-dispatch',
        'forgejo-update',
    ]
    dispatch_metadata = calls[1][1]['metadata']
    assert dispatch_metadata['forgejo_agent_task_id'] == 42
    assert (
        dispatch_metadata['post_clone_task']['metadata'][
            'forgejo_agent_task_id'
        ]
        == 42
    )
    assert calls[2][1]['external_task_id'] == 'codetether-77'
    assert result['forgejo_agent_task_id'] == 42
    assert result['forgejo_agent_task_url'].endswith('/agent/tasks/42')


def test_footer_prefers_native_forgejo_task_url(monkeypatch):
    monkeypatch.setattr(
        completion,
        'build_task_session_url',
        lambda task_id: f'https://codetether.example/session/{task_id}',
    )
    native = 'https://forgejo.example/acme/widgets/agent/tasks/42'
    footer = completion._task_footer(
        'codetether-77', {'forgejo_agent_task_url': native}
    )
    assert f'[View session]({native})' in footer
    assert 'codetether.example' not in footer
