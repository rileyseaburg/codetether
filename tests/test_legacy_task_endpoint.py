from types import SimpleNamespace

import pytest

import a2a_server.monitor_api as monitor


@pytest.mark.asyncio
async def test_non_protocol_endpoint_keeps_public_compatibility(monkeypatch):
    task = monitor.AgentTaskCreate(title='legacy', prompt='data')
    request = SimpleNamespace(headers={})
    captured = []

    async def create(*arguments):
        captured.append(arguments)
        return {'id': 'task'}

    def unexpected_scope(_request):
        raise AssertionError(
            'legacy task must not enter protocol authentication'
        )

    monkeypatch.setattr(monitor, 'forgejo_request_scope', unexpected_scope)
    monkeypatch.setattr(monitor, 'create_global_task', create)
    await monitor.create_global_task_endpoint(task, request)
    assert captured == [(task, '', 'internal:global', None)]
