from __future__ import annotations

import json

import httpx
import pytest

from a2a_server import forgejo_agent_client as client


@pytest.fixture(autouse=True)
def _settings(monkeypatch):
    monkeypatch.setenv('FORGEJO_API_URL', 'https://forgejo.example/api/v1')
    monkeypatch.setenv('FORGEJO_TOKEN', 'top-secret-token')
    monkeypatch.setattr(client, '_HTTP_CLIENT', None)


@pytest.mark.asyncio
async def test_create_update_and_append_event_use_repository_api(monkeypatch):
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        path = request.url.path
        if request.method == 'POST' and path.endswith('/agent/tasks'):
            return httpx.Response(
                201,
                json={
                    'id': 42,
                    'html_url': 'https://forgejo.example/acme/widgets/agent/tasks/42',
                },
            )
        if request.method == 'PATCH':
            return httpx.Response(200, json={'id': 42, 'status': 'running'})
        return httpx.Response(201, json={'id': 99, 'sequence': 1})

    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        'AsyncClient',
        lambda **kwargs: original(transport=transport, **kwargs),
    )

    task = await client.create_task(
        repo='acme/widgets',
        operation='fix',
        prompt='Fix issue 7',
        idempotency_key='issue-7-comment-9',
        issue_index=7,
        metadata={'authorization': 'must-not-leak'},
    )
    assert task['id'] == 42
    await client.update_task(repo='acme/widgets', task_id=42, status='running')
    await client.append_event(
        repo='acme/widgets',
        task_id=42,
        sequence=1,
        external_id='task:1',
        event_type='tool.call',
        payload={'token': 'must-not-leak', 'tool': 'grep'},
    )

    assert [request.url.path for request in requests] == [
        '/api/v1/repos/acme/widgets/agent/tasks',
        '/api/v1/repos/acme/widgets/agent/tasks/42',
        '/api/v1/repos/acme/widgets/agent/tasks/42/events',
    ]
    assert all(
        request.headers['authorization'] == 'token top-secret-token'
        for request in requests
    )
    create_payload = json.loads(requests[0].content)
    assert create_payload['metadata']['authorization'] == '[REDACTED]'
    event_payload = json.loads(requests[2].content)
    assert event_payload['payload']['token'] == '[REDACTED]'


@pytest.mark.asyncio
async def test_publish_session_events_appends_after_existing_stage(monkeypatch):
    appended: list[dict] = []

    async def fake_list(**kwargs):
        return {
            'events': [
                {'sequence': 4, 'external_id': 'older-stage-event'},
                {
                    'sequence': 5,
                    'external_id': client._event_id(
                        'task-2',
                        1,
                        'agent.message',
                        {'role': 'assistant', 'content': 'Already published'},
                    ),
                },
            ]
        }

    async def fake_append(**kwargs):
        appended.append(kwargs)
        return kwargs

    monkeypatch.setattr(client, 'list_events', fake_list)
    monkeypatch.setattr(client, 'append_event', fake_append)

    count = await client.publish_session_events(
        repo='acme/widgets',
        forgejo_task_id=42,
        codetether_task_id='task-2',
        messages=[
            {'role': 'assistant', 'content': 'Already published'},
            {'role': 'assistant', 'content': 'New event'},
        ],
    )

    assert count == 1
    assert len(appended) == 1
    assert appended[0]['sequence'] == 7
    assert appended[0]['payload']['content'] == 'New event'


def test_normalize_session_events_is_ordered_deterministic_and_redacted():
    messages = [
        {
            'role': 'assistant',
            'content': 'Inspecting',
            'authorization': 'secret',
            'tool_calls': [
                {'name': 'grep', 'arguments': {'api_key': 'secret'}},
                {'name': 'bash', 'output': 'ok', 'status': 'completed'},
            ],
        },
        {'role': 'user', 'content': 'Continue'},
    ]
    first = client.normalize_session_events('task-1', messages)
    second = client.normalize_session_events('task-1', messages)

    assert first == second
    assert [event['sequence'] for event in first] == [1, 2, 3, 4]
    assert [event['type'] for event in first] == [
        'agent.message',
        'tool.call',
        'tool.result',
        'user.message',
    ]
    assert first[0]['payload']['authorization'] == '[REDACTED]'
    assert first[1]['payload']['arguments']['api_key'] == '[REDACTED]'
    assert len({event['external_id'] for event in first}) == 4


@pytest.mark.asyncio
async def test_request_reuses_async_client(monkeypatch):
    instances = []

    class Response:
        status_code = 200
        text = ''
        content = b'{}'

        @staticmethod
        def json():
            return {}

    class FakeClient:
        def __init__(self, *, timeout):
            assert timeout == 30
            self.is_closed = False
            self.requests = []
            instances.append(self)

        async def request(self, method, url, **kwargs):
            self.requests.append((method, url, kwargs))
            return Response()

    monkeypatch.setattr(client.httpx, 'AsyncClient', FakeClient)

    await client._request(
        'GET',
        '/repos/acme/widgets/agent/tasks/1',
        base_url='https://forge.example',
    )
    await client._request(
        'GET',
        '/repos/acme/widgets/agent/tasks/2',
        base_url='https://forge.example',
    )

    assert len(instances) == 1
    assert len(instances[0].requests) == 2
    assert instances[0].requests[0][2]['headers']['Authorization'] == (
        'token top-secret-token'
    )
