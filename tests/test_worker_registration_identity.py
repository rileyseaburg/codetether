import pytest

from a2a_server.worker_registration_identity import bind
from tests.forgejo_metadata import metadata
from tests.forgejo_provenance_fixture import registry
from tests.worker_identity_headers import headers


def test_canonical_registration_is_bound_to_key_and_tenant(monkeypatch):
    value = metadata()
    name = str(value['target_agent_name'])
    monkeypatch.setenv('CODETETHER_PROVENANCE_SIGNING_KEYS', registry(value))
    proof = headers('register', 'worker-1', name, '')
    capabilities, tenant = bind(proof, 'worker-1', name, ['base'])
    assert tenant == 'tenant'
    assert 'codetether-identity-key:author-key' in capabilities


def test_canonical_registration_rejects_an_unbound_key(monkeypatch):
    value = metadata()
    monkeypatch.setenv('CODETETHER_PROVENANCE_SIGNING_KEYS', registry(value))
    proof = headers('register', 'worker-1', 'ctforgejo_attacker', '')
    with pytest.raises(ValueError, match='not bound'):
        bind(proof, 'worker-1', 'ctforgejo_attacker', [])
