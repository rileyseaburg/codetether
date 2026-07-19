from types import SimpleNamespace

import pytest

from a2a_server import database, worker_sse
from tests.forgejo_metadata import metadata
from tests.forgejo_provenance_fixture import registry
from tests.worker_identity_headers import headers


@pytest.mark.asyncio
async def test_claim_endpoint_rejects_a_replayed_worker_proof(monkeypatch):
    value = metadata()
    value.update(author_identity_key_id='author-key', tenant_id='tenant')
    name = str(value['target_agent_name'])

    async def task(_task_id: str) -> dict[str, object]:
        return {'metadata': value}

    async def worker(_worker_id: str) -> dict[str, object]:
        return {'name': name}

    monkeypatch.setenv('CODETETHER_PROVENANCE_SIGNING_KEYS', registry(value))
    monkeypatch.setattr(database, 'db_get_task', task)
    monkeypatch.setattr(database, 'db_get_worker', worker)
    monkeypatch.setattr(worker_sse, '_verify_auth', lambda _request: None)
    request = SimpleNamespace(
        headers=headers('claim', 'worker-2', name, 'cttask_1')
    )
    claim = worker_sse.TaskClaimRequest(task_id='cttask_1')
    with pytest.raises(worker_sse.HTTPException) as raised:
        await worker_sse.claim_task(
            request, claim, worker_id=None, x_worker_id='worker-1'
        )
    assert raised.value.status_code == 403  # noqa: PLR2004
