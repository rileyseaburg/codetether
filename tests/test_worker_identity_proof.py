import pytest

from a2a_server.worker_identity_proof import verify
from tests.forgejo_metadata import metadata
from tests.forgejo_provenance_fixture import registry
from tests.worker_identity_headers import headers


def test_matches_the_rust_worker_proof_vector(monkeypatch):
    monkeypatch.setattr(
        'tests.worker_identity_headers.time.time', lambda: 1700000000
    )
    proof = headers('claim', 'worker-1', 'ctforgejo_author', 'cttask_1')
    assert proof['x-codetether-worker-proof'] == (
        'a54f3fd301714efa72dd0be12b5558e9e5d552a8aefac3189955e567ed0814ce'
    )


def test_worker_proof_binds_request_identity_and_resource(monkeypatch):
    value = metadata()
    name = str(value['target_agent_name'])
    monkeypatch.setenv('CODETETHER_PROVENANCE_SIGNING_KEYS', registry(value))
    proof = headers('claim', 'worker-1', name, 'cttask_1')
    key = verify(proof, 'claim', 'worker-1', name, 'cttask_1')
    assert key.agent_identity == name


def test_worker_proof_rejects_replay_for_another_task(monkeypatch):
    value = metadata()
    name = str(value['target_agent_name'])
    monkeypatch.setenv('CODETETHER_PROVENANCE_SIGNING_KEYS', registry(value))
    proof = headers('claim', 'worker-1', name, 'cttask_1')
    with pytest.raises(ValueError, match='invalid'):
        verify(proof, 'claim', 'worker-1', name, 'cttask_2')
