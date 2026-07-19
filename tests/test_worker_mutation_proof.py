import hashlib

import pytest

from fastapi import HTTPException

from a2a_server import database
from a2a_server.forgejo_worker_claim import require
from a2a_server.worker_task_mutation import authorize
from tests.forgejo_metadata import metadata
from tests.forgejo_provenance_fixture import registry
from tests.worker_identity_headers import headers
from tests.worker_signed_request import SignedRequest


@pytest.mark.asyncio
async def test_task_mutation_proof_is_bound_to_its_action(monkeypatch):
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
    proof = headers('release', 'worker-1', name, 'cttask_1')
    await require(proof, 'cttask_1', 'worker-1', action='release')
    with pytest.raises(ValueError):
        await require(proof, 'cttask_1', 'worker-1', action='output')

    body = b'{"task_id":"cttask_1","status":"completed"}'
    resource = f'cttask_1:{hashlib.sha256(body).hexdigest()}'
    release_proof = headers('release', 'worker-1', name, resource)
    await authorize(
        SignedRequest(release_proof, body),
        'release',
        'cttask_1',
        'worker-1',
    )
    with pytest.raises(HTTPException):
        await authorize(
            SignedRequest(release_proof, body + b' '),
            'release',
            'cttask_1',
            'worker-1',
        )
    with pytest.raises(ValueError):
        await require(release_proof, 'cttask_1', 'worker-2', action='release')
