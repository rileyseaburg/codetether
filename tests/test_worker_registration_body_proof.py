import hashlib

import pytest

from a2a_server import monitor_api
from tests.forgejo_metadata import metadata
from tests.forgejo_provenance_fixture import registry
from tests.worker_identity_headers import headers
from tests.worker_signed_request import SignedRequest


def signed_request(name: str, body: bytes = b'{}') -> SignedRequest:
    resource = f'worker-1:{hashlib.sha256(body).hexdigest()}'
    return SignedRequest(headers('register', 'worker-1', name, resource), body)


@pytest.mark.asyncio
async def test_registration_proof_is_bound_to_the_request_body(monkeypatch):
    value = metadata()
    name = str(value['target_agent_name'])

    async def persist(_worker: dict[str, object]) -> bool:
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
    request = signed_request(name)
    try:
        await monitor_api.register_worker(registration, request)
        with pytest.raises(monitor_api.HTTPException) as raised:
            await monitor_api.register_worker(
                registration,
                SignedRequest(request.headers, b'{"tampered":true}'),
            )
        assert raised.value.status_code == 403  # noqa: PLR2004
    finally:
        monitor_api._registered_workers.pop('worker-1', None)  # noqa: SLF001
