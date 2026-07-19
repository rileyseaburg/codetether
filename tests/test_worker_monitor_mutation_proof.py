import pytest

from a2a_server import database, monitor_api
from tests.forgejo_metadata import metadata
from tests.forgejo_provenance_fixture import registry
from tests.worker_identity_headers import headers
from tests.worker_signed_request import SignedRequest


def install(monkeypatch):
    value = metadata()
    value.update(author_identity_key_id='author-key', tenant_id='tenant')
    name = str(value['target_agent_name'])

    async def task(_task_id: str) -> dict[str, object]:
        return {'metadata': value, 'worker_id': 'worker-1', 'status': 'working'}

    async def worker(_worker_id: str) -> dict[str, object]:
        return {'name': name}

    monkeypatch.setenv('CODETETHER_PROVENANCE_SIGNING_KEYS', registry(value))
    monkeypatch.setattr(database, 'db_get_task', task)
    monkeypatch.setattr(database, 'db_get_worker', worker)
    return SignedRequest(headers('claim', 'worker-1', name, 'cttask_1'))


@pytest.mark.asyncio
async def test_status_endpoint_rejects_a_claim_proof_replay(monkeypatch):
    request = install(monkeypatch)
    update = monitor_api.TaskStatusUpdate(
        status='completed', worker_id='worker-1'
    )
    with pytest.raises(monitor_api.HTTPException) as raised:
        await monitor_api.update_task_status('cttask_1', update, request)
    assert raised.value.status_code == 403  # noqa: PLR2004


@pytest.mark.asyncio
async def test_output_endpoint_rejects_a_claim_proof_replay(monkeypatch):
    request = install(monkeypatch)
    chunk = monitor_api.TaskOutputChunk(worker_id='worker-1', output='forged')
    with pytest.raises(monitor_api.HTTPException) as raised:
        await monitor_api.stream_task_output('cttask_1', chunk, request)
    assert raised.value.status_code == 403  # noqa: PLR2004
