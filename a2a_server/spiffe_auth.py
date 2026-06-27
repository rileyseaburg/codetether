"""SPIFFE JWT-SVID authentication for A2A agents and workers.

Validates SPIFFE JWT-SVIDs (https://spiffe.io) presented as
``Authorization: Bearer <jwt-svid>`` and returns the caller's SPIFFE ID.

SPIFFE provides cryptographic, short-lived, auto-rotated workload identity in
place of long-lived shared secrets. A JWT-SVID is a standard JWT whose ``sub``
claim is a SPIFFE ID:

    spiffe://<trust-domain>/<path>
    e.g. spiffe://codetether.io/tenant/acme/agent/marketing-orchestrator

Validation flow:
    1. Parse the Bearer token.
    2. Fetch the trust-domain JWKS (SPIRE OIDC discovery) and verify signature.
    3. Enforce ``aud`` (the SVID must be minted for this server).
    4. Extract the SPIFFE ID from ``sub`` and validate the trust domain.

The resulting SPIFFE ID is intended to be handed to OPA for authorization,
with the path segments mapped to tenant/role. SPIFFE = authentication,
OPA = authorization.

Configuration (env):
    SPIFFE_ENABLED          "true" to enable SVID validation (default false)
    SPIFFE_TRUST_DOMAIN     expected trust domain, e.g. "codetether.io"
    SPIFFE_AUDIENCE         expected audience, e.g. "a2a-server" (comma list ok)
    SPIFFE_JWKS_URL         URL to the JWKS bundle (SPIRE OIDC discovery)
    SPIFFE_JWKS_TTL         JWKS cache TTL seconds (default 300)
    SPIFFE_ALLOW_TOKEN_LEGACY  "true" to also accept legacy A2A_AUTH_TOKENS
                            during migration (default true)
"""

from __future__ import annotations

import logging
import os
import threading
import time

from dataclasses import dataclass

import jwt

from fastapi import HTTPException, Request
from jwt import PyJWKClient


logger = logging.getLogger(__name__)


def _enabled() -> bool:
    return os.environ.get("SPIFFE_ENABLED", "false").lower() == "true"


def spiffe_enabled() -> bool:
    """Public accessor for whether SVID validation is active."""
    return _enabled()


def _trust_domain() -> str:
    return os.environ.get("SPIFFE_TRUST_DOMAIN", "").strip()


def _audiences() -> list[str]:
    raw = os.environ.get("SPIFFE_AUDIENCE", "").strip()
    return [a.strip() for a in raw.split(",") if a.strip()]


def _jwks_url() -> str:
    return os.environ.get("SPIFFE_JWKS_URL", "").strip()


def _jwks_ttl() -> int:
    try:
        return int(os.environ.get("SPIFFE_JWKS_TTL", "300"))
    except ValueError:
        return 300


def allow_token_legacy() -> bool:
    """Whether legacy A2A_AUTH_TOKENS are still accepted during migration."""
    return os.environ.get("SPIFFE_ALLOW_TOKEN_LEGACY", "true").lower() == "true"


def _role_map() -> dict[str, str]:
    """Parse SPIFFE_ROLE_MAP ("svid-role:rbac-role,...") into a dict."""
    raw = os.environ.get("SPIFFE_ROLE_MAP", "").strip()
    mapping: dict[str, str] = {}
    for pair in raw.split(","):
        entry = pair.strip()
        if ":" in entry:
            svid_role, rbac_role = entry.split(":", 1)
            svid_role = svid_role.strip()
            rbac_role = rbac_role.strip()
            if svid_role and rbac_role:
                mapping[svid_role] = rbac_role
    return mapping


def _default_rbac_role() -> str:
    """Default RBAC role for SPIFFE callers without an explicit mapping."""
    role = os.environ.get("SPIFFE_DEFAULT_ROLE", "a2a-agent").strip()
    return role or "a2a-agent"


def _mapped_rbac_roles(svid_role: str | None) -> list[str]:
    """Map a SPIFFE path role to application RBAC roles."""
    mapping = _role_map()
    if svid_role and svid_role in mapping:
        return [mapping[svid_role]]
    return [_default_rbac_role()]


# Mutable cache state held in a dict to avoid module-level `global` rebinds.
_jwk_cache: dict = {"client": None, "at": 0.0}
_jwk_lock = threading.Lock()


def _get_jwk_client() -> PyJWKClient:
    """Return a cached PyJWKClient, rotating it past the configured TTL."""
    url = _jwks_url()
    if not url:
        raise HTTPException(
            status_code=500, detail="SPIFFE_JWKS_URL not configured"
        )
    now = time.monotonic()
    with _jwk_lock:
        client = _jwk_cache["client"]
        if client is None or (now - _jwk_cache["at"]) > _jwks_ttl():
            client = PyJWKClient(url, cache_keys=True)
            _jwk_cache["client"] = client
            _jwk_cache["at"] = now
        return client


@dataclass(frozen=True)
class SpiffeIdentity:
    """A parsed SPIFFE ID plus convenience accessors for OPA mapping."""

    spiffe_id: str
    trust_domain: str
    path: str
    claims: dict

    @property
    def segments(self) -> list[str]:
        return [s for s in self.path.split("/") if s]

    @property
    def tenant(self) -> str | None:
        segs = self.segments
        for i, seg in enumerate(segs):
            if seg == "tenant" and i + 1 < len(segs):
                return segs[i + 1]
        return None

    @property
    def role(self) -> str | None:
        segs = self.segments
        for kw in ("agent", "worker", "server", "service"):
            if kw in segs:
                idx = segs.index(kw)
                if idx + 1 < len(segs):
                    return segs[idx + 1]
                return kw
        return None

    def to_opa_input(self) -> dict:
        return {
            "spiffe_id": self.spiffe_id,
            "trust_domain": self.trust_domain,
            "tenant": self.tenant,
            "role": self.role,
            "path": self.path,
        }

    def to_policy_user(self) -> dict:
        """Build the ``user`` dict consumed by ``a2a_server.policy``.

        The SPIFFE path role (e.g. the segment after ``agent``/``worker``)
        is mapped to an application RBAC role via ``SPIFFE_ROLE_MAP``
        (``svid-role:rbac-role`` comma list). Unmapped callers default to
        the ``a2a-agent`` service-account role. ``auth_source`` is set to
        ``spiffe`` so policy code can branch on workload identity.
        """
        rbac_roles = _mapped_rbac_roles(self.role)
        return {
            "user_id": self.spiffe_id,
            "sub": self.spiffe_id,
            "roles": rbac_roles,
            "tenant_id": self.tenant,
            "scopes": [],
            "auth_source": "spiffe",
            "spiffe_id": self.spiffe_id,
        }


def parse_spiffe_id(spiffe_id: str) -> tuple[str, str]:
    """Split a spiffe://trust-domain/path URI into (trust_domain, path)."""
    if not spiffe_id.startswith("spiffe://"):
        raise ValueError("SPIFFE ID must start with spiffe://")
    remainder = spiffe_id[len("spiffe://"):]
    if not remainder:
        raise ValueError("SPIFFE ID missing trust domain")
    if "/" in remainder:
        trust_domain, path = remainder.split("/", 1)
        path = "/" + path
    else:
        trust_domain, path = remainder, "/"
    if not trust_domain:
        raise ValueError("SPIFFE ID missing trust domain")
    return trust_domain, path


def validate_jwt_svid(token: str) -> SpiffeIdentity:
    """Validate a JWT-SVID and return the parsed SpiffeIdentity.

    Raises HTTPException(401/403) on any validation failure.
    """
    try:
        signing_key = _get_jwk_client().get_signing_key_from_jwt(token)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("SVID signing key lookup failed: %s", exc)
        raise HTTPException(
            status_code=401, detail="Invalid SVID signature"
        ) from exc

    audiences = _audiences()
    decode_kwargs: dict = {
        "algorithms": ["RS256", "ES256", "ES384", "EdDSA"],
        "options": {"require": ["exp", "sub"]},
    }
    if audiences:
        decode_kwargs["audience"] = audiences
    else:
        decode_kwargs["options"]["verify_aud"] = False

    try:
        claims = jwt.decode(token, signing_key.key, **decode_kwargs)
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="SVID expired") from exc
    except jwt.InvalidAudienceError as exc:
        raise HTTPException(
            status_code=403, detail="SVID audience mismatch"
        ) from exc
    except jwt.PyJWTError as exc:
        logger.warning("SVID decode failed: %s", exc)
        raise HTTPException(status_code=401, detail="Invalid SVID") from exc

    spiffe_id = claims.get("sub", "")
    try:
        trust_domain, path = parse_spiffe_id(spiffe_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=403, detail=f"Invalid SPIFFE ID: {exc}"
        ) from exc

    expected_td = _trust_domain()
    if expected_td and trust_domain != expected_td:
        raise HTTPException(
            status_code=403,
            detail=f"Untrusted SPIFFE trust domain: {trust_domain}",
        )

    return SpiffeIdentity(
        spiffe_id=spiffe_id,
        trust_domain=trust_domain,
        path=path,
        claims=claims,
    )


def bearer_token(request: Request) -> str | None:
    """Extract the raw Bearer credential from the request, if present."""
    auth = (
        request.headers.get("authorization")
        or request.headers.get("Authorization")
        or ""
    )
    if not auth.startswith("Bearer "):
        return None
    token = auth.removeprefix("Bearer ").strip()
    return token or None


def verify_spiffe(request: Request) -> SpiffeIdentity | None:
    """Validate the request's JWT-SVID; return identity or None if disabled."""
    if not _enabled():
        return None
    token = bearer_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Missing Bearer SVID")
    return validate_jwt_svid(token)
