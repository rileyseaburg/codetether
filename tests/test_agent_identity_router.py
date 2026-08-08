import pytest


router = pytest.importorskip('a2a_server.agent_identity_api').router


def test_admin_bundle_exposes_agent_identity_endpoint():
    routes = {
        (route.path, tuple(route.methods or ())) for route in router.routes
    }
    assert ('/v1/admin/agent-identities', ('POST',)) in routes
