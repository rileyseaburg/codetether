import pytest

from a2a_server import database, worker_progress_routes
from tests.forgejo_metadata import metadata
from tests.forgejo_provenance_fixture import registry
from tests.worker_identity_headers import headers
from tests.worker_signed_request import SignedRequest


@pytest.mark.asyncio
async def test_extended_heartbeat_rejects_a_claim_proof_replay(monkeypatch):
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
    monkeypatch.setattr(
        worker_progress_routes, 'verify_auth', lambda _request: None
    )
    request = SignedRequest(headers('claim', 'worker-1', name, 'cttask_1'))
    heartbeat = worker_progress_routes.ExtendedHeartbeatRequest(
        task_id='cttask_1', worker_id='worker-1'
    )
    with pytest.raises(worker_progress_routes.HTTPException) as raised:
        await worker_progress_routes.heartbeat_extended_endpoint(
            request, heartbeat
        )
    assert raised.value.status_code == 403  # noqa: PLR2004
    with pytest.raises(worker_progress_routes.HTTPException):
        await worker_progress_routes.post_extended_heartbeat(request, heartbeat)
    regular = worker_progress_routes.TaskHeartbeatRequest(
        task_id='cttask_1', worker_id='worker-1'
    )
    with pytest.raises(worker_progress_routes.HTTPException):
        await worker_progress_routes.post_task_heartbeat(request, regular)
    resume = worker_progress_routes.TaskResumeRequest(
        task_id='cttask_1', worker_id='worker-1'
    )
    with pytest.raises(worker_progress_routes.HTTPException):
        await worker_progress_routes.resume_task_from_checkpoint(
            request, resume
        )
