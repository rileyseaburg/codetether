import hashlib

import pytest

from a2a_server import monitor_api
from tests.forgejo_metadata import metadata
from tests.forgejo_provenance_fixture import registry
from tests.worker_identity_headers import headers
from tests.worker_signed_request import SignedRequest


@pytest.mark.asyncio
async def test_canonical_registration_fails_when_storage_does(monkeypatch):
    value = metadata()
    name = str(value['target_agent_name'])

    async def fail(_worker: dict[str, object]) -> bool:
        return False

    monkeypatch.setenv('CODETETHER_PROVENANCE_SIGNING_KEYS', registry(value))
    monkeypatch.setattr(monitor_api.db, 'db_upsert_worker', fail)
    registration = monitor_api.WorkerRegistration(
        worker_id='worker-2', name=name
    )
    body = b'{}'
    resource = f'worker-2:{hashlib.sha256(body).hexdigest()}'
    request = SignedRequest(
        headers('register', 'worker-2', name, resource), body
    )
    with pytest.raises(monitor_api.HTTPException) as raised:
        await monitor_api.register_worker(registration, request)
    assert raised.value.status_code == 503  # noqa: PLR2004
    assert 'worker-2' not in monitor_api._registered_workers  # noqa: SLF001
