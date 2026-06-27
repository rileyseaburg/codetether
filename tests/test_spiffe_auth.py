"""Tests for SPIFFE JWT-SVID authentication (a2a_server/spiffe_auth.py)."""

import time

import jwt
import pytest

from cryptography.hazmat.primitives.asymmetric import rsa

from a2a_server import spiffe_auth


# ── Test key material ────────────────────────────────────────────

_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_KID = "test-kid-1"

# HTTP status codes used in assertions.
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403


def _make_svid(sub, aud="a2a-server", exp_delta=300):
    return jwt.encode(
        {"sub": sub, "aud": aud, "exp": int(time.time()) + exp_delta},
        _KEY,
        algorithm="RS256",
        headers={"kid": _KID},
    )


class _FakeSigningKey:
    key = _KEY.public_key()


class _FakeJwkClient:
    @staticmethod
    def get_signing_key_from_jwt(_token):
        return _FakeSigningKey()


@pytest.fixture(autouse=True)
def _env_and_jwks(monkeypatch):
    monkeypatch.setenv("SPIFFE_ENABLED", "true")
    monkeypatch.setenv("SPIFFE_TRUST_DOMAIN", "codetether.io")
    monkeypatch.setenv("SPIFFE_AUDIENCE", "a2a-server")
    monkeypatch.setenv("SPIFFE_JWKS_URL", "https://spire.example/keys")
    # Bypass the network JWKS fetch: return our public key for any token.
    monkeypatch.setattr(spiffe_auth, "_get_jwk_client", _FakeJwkClient)
    yield


# ── parse_spiffe_id ──────────────────────────────────────────────

def test_parse_spiffe_id_with_path():
    td, path = spiffe_auth.parse_spiffe_id(
        "spiffe://codetether.io/tenant/acme/agent/orch"
    )
    assert td == "codetether.io"
    assert path == "/tenant/acme/agent/orch"


def test_parse_spiffe_id_root():
    td, path = spiffe_auth.parse_spiffe_id("spiffe://codetether.io")
    assert td == "codetether.io"
    assert path == "/"


def test_parse_spiffe_id_rejects_non_spiffe():
    with pytest.raises(ValueError):
        spiffe_auth.parse_spiffe_id("https://codetether.io/x")


# ── SpiffeIdentity mapping ───────────────────────────────────────

def test_identity_tenant_and_role():
    ident = spiffe_auth.SpiffeIdentity(
        "spiffe://codetether.io/tenant/acme/agent/orch",
        "codetether.io", "/tenant/acme/agent/orch", {},
    )
    assert ident.tenant == "acme"
    assert ident.role == "orch"


def test_identity_worker_role_no_tenant():
    ident = spiffe_auth.SpiffeIdentity(
        "spiffe://codetether.io/worker/pool",
        "codetether.io", "/worker/pool", {},
    )
    assert ident.tenant is None
    assert ident.role == "pool"


# ── to_policy_user (OPA mapping) ─────────────────────────────────

def test_to_policy_user_default_role():
    ident = spiffe_auth.SpiffeIdentity(
        "spiffe://codetether.io/tenant/acme/agent/orch",
        "codetether.io", "/tenant/acme/agent/orch", {},
    )
    user = ident.to_policy_user()
    assert user["roles"] == ["a2a-agent"]
    assert user["tenant_id"] == "acme"
    assert user["auth_source"] == "spiffe"
    assert user["spiffe_id"] == "spiffe://codetether.io/tenant/acme/agent/orch"


def test_to_policy_user_mapped_role(monkeypatch):
    monkeypatch.setenv("SPIFFE_ROLE_MAP", "orch:operator,reader:viewer")
    ident = spiffe_auth.SpiffeIdentity(
        "spiffe://codetether.io/tenant/acme/agent/orch",
        "codetether.io", "/tenant/acme/agent/orch", {},
    )
    assert ident.to_policy_user()["roles"] == ["operator"]


def test_to_policy_user_custom_default(monkeypatch):
    monkeypatch.setenv("SPIFFE_DEFAULT_ROLE", "viewer")
    ident = spiffe_auth.SpiffeIdentity(
        "spiffe://codetether.io/worker/pool",
        "codetether.io", "/worker/pool", {},
    )
    assert ident.to_policy_user()["roles"] == ["viewer"]


# ── validate_jwt_svid ────────────────────────────────────────────

def test_validate_valid_svid():
    token = _make_svid("spiffe://codetether.io/tenant/acme/agent/orch")
    ident = spiffe_auth.validate_jwt_svid(token)
    assert ident.spiffe_id == "spiffe://codetether.io/tenant/acme/agent/orch"
    assert ident.tenant == "acme"


def test_validate_rejects_expired():
    token = _make_svid("spiffe://codetether.io/x", exp_delta=-10)
    with pytest.raises(Exception) as exc:
        spiffe_auth.validate_jwt_svid(token)
    assert getattr(exc.value, "status_code", None) == HTTP_UNAUTHORIZED


def test_validate_rejects_wrong_audience():
    token = _make_svid("spiffe://codetether.io/x", aud="other-service")
    with pytest.raises(Exception) as exc:
        spiffe_auth.validate_jwt_svid(token)
    assert getattr(exc.value, "status_code", None) == HTTP_FORBIDDEN


def test_validate_rejects_wrong_trust_domain():
    token = _make_svid("spiffe://evil.example/x")
    with pytest.raises(Exception) as exc:
        spiffe_auth.validate_jwt_svid(token)
    assert getattr(exc.value, "status_code", None) == HTTP_FORBIDDEN
