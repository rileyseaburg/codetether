import pytest

from a2a_server import database, worker_sse
from tests.forgejo_metadata import metadata
from tests.forgejo_provenance_fixture import registry
from tests.worker_identity_headers import headers
from tests.worker_signed_request import SignedRequest


@pytest.mark.asyncio
async def test_release_endpoint_rejects_a_claim_proof_replay(monkeypatch):
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
    monkeypatch.setattr(worker_sse, '_verify_auth', lambda _request: None)
    request = SignedRequest(headers('claim', 'worker-1', name, 'cttask_1'))
    release = worker_sse.TaskReleaseRequest(
        task_id='cttask_1', status='completed'
    )
    with pytest.raises(worker_sse.HTTPException) as raised:
        await worker_sse.release_task(
            request, release, worker_id=None, x_worker_id='worker-1'
        )
    assert raised.value.status_code == 403  # noqa: PLR2004
