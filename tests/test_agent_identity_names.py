from a2a_server.agent_identity_names import workload_identity


MAX_SERVICE_ACCOUNT_LENGTH = 63
MAX_FORGEJO_USERNAME_LENGTH = 40


def test_workload_identity_is_stable_and_spire_compatible(monkeypatch):
    monkeypatch.setenv('SPIFFE_TRUST_DOMAIN', 'codetether.io')
    monkeypatch.setenv('AGENT_IDENTITY_NAMESPACE', 'a2a-server')
    first = workload_identity('hire-42', 'Engineering Manager')
    replay = workload_identity('hire-42', 'Engineering Manager')
    assert first == replay
    assert len(first.service_account) <= MAX_SERVICE_ACCOUNT_LENGTH
    assert len(first.username) <= MAX_FORGEJO_USERNAME_LENGTH
    assert first.spiffe_id == (
        f'spiffe://codetether.io/ns/a2a-server/sa/{first.service_account}'
    )
    assert first.email.endswith('@agents.invalid')
