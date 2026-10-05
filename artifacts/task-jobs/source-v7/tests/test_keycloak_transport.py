from a2a_server.keycloak_transport import is_secure_keycloak_transport


def test_https_transport_is_accepted():
    assert is_secure_keycloak_transport('https://auth.example.com')


def test_cluster_local_http_transport_is_accepted():
    assert is_secure_keycloak_transport(
        'http://keycloak.keycloak.svc.cluster.local:8080'
    )


def test_external_http_transport_is_rejected():
    assert not is_secure_keycloak_transport('http://auth.example.com')


def test_incomplete_transport_is_rejected():
    assert not is_secure_keycloak_transport('https:///missing-host')
