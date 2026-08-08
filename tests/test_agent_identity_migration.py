from pathlib import Path


def test_identity_binding_migration_has_immutable_keys():
    sql = Path(
        'a2a_server/migrations/036_agent_identity_bindings.sql'
    ).read_text()
    assert 'provisioning_id TEXT NOT NULL UNIQUE' in sql
    assert 'spiffe_id TEXT NOT NULL UNIQUE' in sql
    assert 'keycloak_subject TEXT NOT NULL UNIQUE' in sql
    assert 'policy_binding_id TEXT NOT NULL UNIQUE' in sql
