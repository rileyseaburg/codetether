import pytest

from a2a_server import monitor_api
from tests.forgejo_metadata import metadata
from tests.forgejo_provenance_fixture import registry
from tests.worker_identity_headers import headers
from tests.worker_signed_request import SignedRequest


@pytest.mark.asyncio
async def test_unregister_rejects_a_registration_proof(monkeypatch):
    value = metadata()
    name = str(value['target_agent_name'])

    async def worker(_worker_id: str) -> dict[str, object]:
        return {'name': name, 'capabilities': []}

    monkeypatch.setenv('CODETETHER_PROVENANCE_SIGNING_KEYS', registry(value))
    monkeypatch.setattr(monitor_api.db, 'db_get_worker', worker)
    request = SignedRequest(headers('register', 'worker-1', name, ''))
    with pytest.raises(monitor_api.HTTPException) as raised:
        await monitor_api.unregister_worker('worker-1', request)
    assert raised.value.status_code == 403  # noqa: PLR2004
