import pytest

from a2a_server.worker_heartbeat_identity import bind
from tests.forgejo_metadata import metadata
from tests.forgejo_provenance_fixture import registry
from tests.worker_identity_headers import headers


def test_canonical_heartbeat_requires_a_fresh_action_bound_proof(monkeypatch):
    value = metadata()
    name = str(value['target_agent_name'])
    worker = {'name': name, 'capabilities': []}
    monkeypatch.setenv('CODETETHER_PROVENANCE_SIGNING_KEYS', registry(value))
    proof = headers('heartbeat', 'worker-1', name, '')
    bound = bind(proof, 'worker-1', worker)
    assert bound['tenant_id'] == 'tenant'
    with pytest.raises(ValueError):
        bind(headers('register', 'worker-1', name, ''), 'worker-1', worker)
