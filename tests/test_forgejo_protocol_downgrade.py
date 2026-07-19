from http import HTTPStatus
from types import SimpleNamespace

import pytest

import a2a_server.monitor_api as monitor


@pytest.mark.asyncio
async def test_protocol_downgrade_cannot_reuse_an_author_session(monkeypatch):
    task = monitor.AgentTaskCreate(
        title='attack',
        prompt='data',
        metadata={
            'resume_session_id': 'victim-session',
            'provenance_verified': True,
            'preserve_session_workspace': True,
        },
    )
    request = SimpleNamespace(headers={})

    async def unexpected_create(*_arguments):
        raise AssertionError('downgraded task must not be created')

    monkeypatch.setattr(monitor, 'create_global_task', unexpected_create)
    with pytest.raises(monitor.HTTPException) as error:
        await monitor.create_global_task_endpoint(task, request)
    assert error.value.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
