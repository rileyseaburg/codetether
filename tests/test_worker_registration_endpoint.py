import hashlib

import pytest

from a2a_server import monitor_api
from tests.forgejo_metadata import metadata
from tests.forgejo_provenance_fixture import registry
from tests.worker_identity_headers import headers
from tests.worker_signed_request import SignedRequest


@pytest.mark.asyncio
async def test_canonical_registration_persists_verified_tenant(monkeypatch):
    value = metadata()
    name = str(value['target_agent_name'])
    seen: dict[str, object] = {}

    async def persist(worker: dict[str, object]) -> bool:
        seen.update(worker)
        return True

    async def no_op(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setenv('CODETETHER_PROVENANCE_SIGNING_KEYS', registry(value))
    monkeypatch.setattr(monitor_api.db, 'db_upsert_worker', persist)
    monkeypatch.setattr(monitor_api, '_redis_upsert_worker', no_op)
    monkeypatch.setattr(monitor_api.monitoring_service, 'log_message', no_op)
    registration = monitor_api.WorkerRegistration(
        worker_id='worker-1', name=name
    )
    body = b'{}'
    resource = f'worker-1:{hashlib.sha256(body).hexdigest()}'
    request = SignedRequest(
        headers('register', 'worker-1', name, resource), body
    )
    try:
        await monitor_api.register_worker(registration, request)
    finally:
        monitor_api._registered_workers.pop('worker-1', None)  # noqa: SLF001
    assert seen['tenant_id'] == 'tenant'
    assert 'codetether-identity-key:author-key' in seen['capabilities']
