from a2a_server.keycloak_issuer import issuer_for_realm


def test_issuer_defaults_to_transport_url(monkeypatch):
    monkeypatch.delenv('KEYCLOAK_ISSUER', raising=False)

    issuer = issuer_for_realm('quantum-forge', 'http://keycloak:8080/')

    assert issuer == 'http://keycloak:8080/realms/quantum-forge'


def test_public_issuer_is_independent_of_transport(monkeypatch):
    monkeypatch.setenv(
        'KEYCLOAK_ISSUER',
        'https://auth.quantum-forge.io/realms/quantum-forge',
    )

    issuer = issuer_for_realm('quantum-forge', 'http://keycloak:8080')

    assert issuer == 'https://auth.quantum-forge.io/realms/quantum-forge'


def test_public_issuer_tracks_token_realm(monkeypatch):
    monkeypatch.setenv(
        'KEYCLOAK_ISSUER',
        'https://auth.quantum-forge.io/realms/quantum-forge',
    )

    issuer = issuer_for_realm('customer-realm', 'http://keycloak:8080')

    assert issuer == 'https://auth.quantum-forge.io/realms/customer-realm'
