import pytest

import a2a_server.forgejo_author_service as service

from tests.forgejo_service_fixture import (
    RecordingBridge,
    request,
)
from tests.forgejo_service_stubs import install


@pytest.mark.asyncio
async def test_create_holds_gate_and_requires_persistence(monkeypatch):
    events = []

    validate = install(monkeypatch, events)
    task = await service.create(
        RecordingBridge(events),
        request(
            {
                'model': 'test',
                'idempotency_scope': 'token:reviewer:fingerprint',
                'tenant_id': 'tenant',
            },
            'forgejo-token',
        ),
        validate,
    )
    assert task['task_id'] == 'cttask_fixed'
    assert task['model'] == 'test'
    assert task['require_persistence'] is True
    assert 'forgejo-token' not in str(task)
    assert 'idempotency_scope' not in task['metadata']
    assert task['metadata']['tenant_id'] == 'tenant'
    assert task['metadata']['server_author_binding_verified'] is True
    assert events == ['verify', 'lock', 'validate', 'create', 'unlock']
