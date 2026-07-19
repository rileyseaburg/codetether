import pytest

from a2a_server import database
from a2a_server.forgejo_worker_claim import require
from tests.forgejo_metadata import metadata
from tests.forgejo_provenance_fixture import registry
from tests.worker_identity_headers import headers


@pytest.mark.asyncio
async def test_author_task_claim_requires_the_bound_worker_key(monkeypatch):
    value = metadata()
    value.update(author_identity_key_id='author-key', tenant_id='tenant')
    name = str(value['target_agent_name'])

    async def task(_task_id):
        return {'metadata': value}

    async def worker(_worker_id):
        return {'name': name}

    monkeypatch.setenv('CODETETHER_PROVENANCE_SIGNING_KEYS', registry(value))
    monkeypatch.setattr(database, 'db_get_task', task)
    monkeypatch.setattr(database, 'db_get_worker', worker)
    proof = headers('claim', 'worker-1', name, 'cttask_1')
    await require(proof, 'cttask_1', 'worker-1')


@pytest.mark.asyncio
async def test_author_task_claim_rejects_another_worker(monkeypatch):
    value = metadata()
    value.update(author_identity_key_id='author-key', tenant_id='tenant')

    async def task(_task_id):
        return {'metadata': value}

    async def worker(_worker_id):
        return {'name': 'ctforgejo_attacker'}

    monkeypatch.setenv('CODETETHER_PROVENANCE_SIGNING_KEYS', registry(value))
    monkeypatch.setattr(database, 'db_get_task', task)
    monkeypatch.setattr(database, 'db_get_worker', worker)
    proof = headers('claim', 'worker-2', 'ctforgejo_attacker', 'cttask_1')
    with pytest.raises(ValueError):
        await require(proof, 'cttask_1', 'worker-2')
