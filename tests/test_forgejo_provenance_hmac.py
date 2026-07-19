import pytest

from a2a_server.forgejo_provenance_fields import parse
from a2a_server.forgejo_provenance_verification import verify
from tests.forgejo_metadata import commit_message, metadata
from tests.forgejo_provenance_fixture import registry


def test_fixture_matches_the_rust_provenance_hmac_vector():
    value = metadata()
    assert parse(commit_message(value))['CodeTether-Signature'] == (
        '72bc4744ef5ec3461ed0279c9a0d716d12b87d29e711dd8f6263cfe7149005be'
    )


def test_provenance_hmac_binds_session_agent_and_tenant(monkeypatch):
    value = metadata()
    monkeypatch.setenv('CODETETHER_PROVENANCE_SIGNING_KEYS', registry(value))
    key = verify(commit_message(value), value)
    assert key.agent_identity == value['target_agent_name']
    assert key.tenant_id == 'tenant'


@pytest.mark.parametrize('field', ['resume_session_id', 'target_agent_name'])
def test_provenance_hmac_rejects_tampered_metadata(monkeypatch, field):
    signed, forwarded = metadata(), metadata()
    monkeypatch.setenv('CODETETHER_PROVENANCE_SIGNING_KEYS', registry(signed))
    forwarded[field] = 'attacker-value'
    with pytest.raises(ValueError):
        verify(commit_message(signed), forwarded)


def test_provenance_hmac_rejects_unconfigured_keys(monkeypatch):
    monkeypatch.delenv('CODETETHER_PROVENANCE_SIGNING_KEYS', raising=False)
    value = metadata()
    with pytest.raises(RuntimeError, match='not configured'):
        verify(commit_message(value), value)
