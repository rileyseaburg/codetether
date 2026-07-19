from types import SimpleNamespace

import pytest

from a2a_server import monitor_api
from tests.forgejo_metadata import metadata
from tests.forgejo_provenance_fixture import registry
from tests.worker_identity_headers import headers


@pytest.mark.asyncio
async def test_canonical_heartbeat_endpoint_verifies_liveness(monkeypatch):
    value = metadata()
    name = str(value['target_agent_name'])
    worker = {'worker_id': 'worker-1', 'name': name, 'capabilities': []}

    async def updated(_worker_id: str) -> bool:
        return True

    async def no_op(_worker: dict[str, object]) -> None:
        return None

    monkeypatch.setenv('CODETETHER_PROVENANCE_SIGNING_KEYS', registry(value))
    monkeypatch.setattr(monitor_api.db, 'db_update_worker_heartbeat', updated)
    monkeypatch.setattr(monitor_api, '_redis_upsert_worker', no_op)
    monitor_api._registered_workers['worker-1'] = worker  # noqa: SLF001
    invalid = SimpleNamespace(headers=headers('register', 'worker-1', name, ''))
    valid = SimpleNamespace(headers=headers('heartbeat', 'worker-1', name, ''))
    try:
        with pytest.raises(monitor_api.HTTPException) as raised:
            await monitor_api.worker_heartbeat('worker-1', invalid)
        assert raised.value.status_code == 403  # noqa: PLR2004
        assert await monitor_api.worker_heartbeat('worker-1', valid) == {
            'success': True
        }
    finally:
        monitor_api._registered_workers.pop('worker-1', None)  # noqa: SLF001
