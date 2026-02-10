"""
OPA Policy Engine Client for A2A Server.

Provides centralized authorization via Open Policy Agent (OPA).
Replaces scattered inline if-checks with declarative Rego policies.

Usage:
    from a2a_server.policy import require_permission

    @router.get("/tasks")
    async def list_tasks(user=Depends(require_permission("tasks:read"))):
        ...

    @router.post("/tasks")
    async def create_task(user=Depends(require_permission("tasks:write"))):
        ...

    # Resource-level check:
    from a2a_server.policy import enforce_policy
    await enforce_policy(user, "tasks:write", resource={"type": "task", "id": task_id, "owner_id": owner, "tenant_id": tid})
"""

import os
import json
import time
import logging
from typing import Optional, Dict, Any, Callable, List
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import httpx
from fastapi import HTTPException, Depends, Request, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────

OPA_URL = os.environ.get("OPA_URL", "http://localhost:8181")
OPA_AUTHZ_PATH = os.environ.get("OPA_AUTHZ_PATH", "v1/data/authz/allow")
OPA_TENANT_PATH = os.environ.get("OPA_TENANT_PATH", "v1/data/tenants/allow")
OPA_TIMEOUT = float(os.environ.get("OPA_TIMEOUT", "2.0"))

# When OPA is unreachable, fail open (allow) or closed (deny).
# Default: closed (deny) for security.
OPA_FAIL_OPEN = os.environ.get("OPA_FAIL_OPEN", "false").lower() == "true"

# Decision cache TTL in seconds (0 = disabled).
OPA_CACHE_TTL = float(os.environ.get("OPA_CACHE_TTL", "5.0"))

# For local/dev mode: evaluate policies in-process without OPA sidecar.
OPA_LOCAL_MODE = os.environ.get("OPA_LOCAL_MODE", "false").lower() == "true"

# Master toggle: set to "false" to disable all policy enforcement.
OPA_ENABLED = os.environ.get("OPA_ENABLED", "true").lower() == "true"

# Path to policies directory (for local mode and bundle building).
POLICIES_DIR = Path(__file__).parent.parent / "policies"


# ── Decision cache ───────────────────────────────────────────────

class _DecisionCache:
    """Simple TTL cache for OPA decisions. Thread-safe via GIL."""

    def __init__(self, ttl: float):
        self._ttl = ttl
        self._store: Dict[str, tuple] = {}  # key → (result, timestamp)

    def get(self, key: str) -> Optional[bool]:
        if self._ttl <= 0:
            return None
        entry = self._store.get(key)
        if entry and (time.monotonic() - entry[1]) < self._ttl:
            return entry[0]
        return None

    def put(self, key: str, result: bool) -> None:
        if self._ttl <= 0:
            return
        self._store[key] = (result, time.monotonic())
        # Evict stale entries periodically.
        if len(self._store) > 10000:
            cutoff = time.monotonic() - self._ttl
            self._store = {
                k: v for k, v in self._store.items() if v[1] > cutoff
            }


_cache = _DecisionCache(OPA_CACHE_TTL)

# ── Local policy data (for local mode) ──────────────────────────

_local_policy_data: Optional[Dict[str, Any]] = None


def _load_local_policy_data() -> Dict[str, Any]:
    """Load data.json for local policy evaluation."""
    global _local_policy_data
    if _local_policy_data is None:
        data_file = POLICIES_DIR / "data.json"
        if data_file.exists():
            with open(data_file) as f:
                _local_policy_data = json.load(f)
        else:
            logger.warning(f"Policy data file not found: {data_file}")
            _local_policy_data = {"roles": {}, "public_endpoints": []}
    return _local_policy_data


def _evaluate_local(
    user: Dict[str, Any],
    action: str,
    resource: Optional[Dict[str, Any]] = None,
) -> tuple:
    """Evaluate authorization locally without OPA sidecar.

    Returns (allowed: bool, reasons: list[str]).
    """
    data = _load_local_policy_data()
    resource = resource or {}
    reasons: List[str] = []

    # Public endpoints.
    if action in data.get("public_endpoints", []):
        return True, []

    # Resolve effective roles (with inheritance).
    effective_roles = set()
    user_roles = user.get("roles", [])
    for role in user_roles:
        role_def = data.get("roles", {}).get(role)
        if not role_def:
            continue
        parent = role_def.get("inherits")
        if parent:
            effective_roles.add(parent)
        else:
            effective_roles.add(role)

    # Collect permissions from effective roles.
    role_permissions = set()
    for role in effective_roles:
        role_def = data.get("roles", {}).get(role)
        if role_def:
            role_permissions.update(role_def.get("permissions", []))

    # Check role-based access.
    if action not in role_permissions:
        reasons.append("no matching role permission")
        return False, reasons

    # API key scope enforcement.
    auth_source = _detect_auth_source(user)
    if auth_source == "api_key":
        scopes = user.get("api_key_scopes") or user.get("scopes", [])
        scope_ok = action in scopes
        if not scope_ok:
            # Check wildcard scopes.
            parts = action.split(":")
            if len(parts) == 2:
                wildcard = f"{parts[0]}:*"
                scope_ok = wildcard in scopes
        if not scope_ok:
            reasons.append("api key scope does not permit action")
            return False, reasons

    # Tenant isolation.
    resource_tenant = resource.get("tenant_id")
    user_tenant = user.get("tenant_id")
    is_admin = bool(effective_roles & {"admin"})

    if resource_tenant and user_tenant and resource_tenant != user_tenant:
        if not is_admin:
            reasons.append("cross-tenant access denied")
            return False, reasons

    return True, reasons


# ── OPA HTTP client ──────────────────────────────────────────────

# Persistent client for connection pooling.
_http_client: Optional[httpx.AsyncClient] = None


async def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            base_url=OPA_URL,
            timeout=OPA_TIMEOUT,
        )
    return _http_client


def _build_input(
    user: Dict[str, Any],
    action: str,
    resource: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build the OPA input document from user context and request."""
    return {
        "input": {
            "user": {
                "user_id": user.get("user_id") or user.get("id") or user.get("sub", ""),
                "roles": user.get("roles", []),
                "tenant_id": user.get("tenant_id"),
                "scopes": user.get("api_key_scopes") or user.get("scopes", []),
                "auth_source": _detect_auth_source(user),
            },
            "action": action,
            "resource": resource or {},
        }
    }


def _detect_auth_source(user: Dict[str, Any]) -> str:
    """Determine how the user authenticated."""
    if user.get("api_key_scopes") is not None:
        return "api_key"
    if user.get("type") == "keycloak" or user.get("keycloak_sub"):
        return "keycloak"
    return "self-service"


def _cache_key(user: Dict[str, Any], action: str, resource: Optional[Dict[str, Any]]) -> str:
    """Build a deterministic cache key."""
    uid = user.get("user_id") or user.get("id") or user.get("sub", "")
    tid = user.get("tenant_id") or ""
    rid = ""
    rtid = ""
    if resource:
        rid = resource.get("id", "")
        rtid = resource.get("tenant_id", "")
    return f"{uid}:{action}:{tid}:{rid}:{rtid}"


# ── Public API ───────────────────────────────────────────────────


async def check_policy(
    user: Dict[str, Any],
    action: str,
    resource: Optional[Dict[str, Any]] = None,
) -> bool:
    """Check if the user is allowed to perform the action.

    Returns True if allowed, False if denied.
    Does not raise — use enforce_policy() to get HTTP 403 on denial.
    """
    # Master toggle: skip enforcement entirely.
    if not OPA_ENABLED:
        return True

    # Check cache first.
    ck = _cache_key(user, action, resource)
    cached = _cache.get(ck)
    if cached is not None:
        return cached

    # Local mode: evaluate in-process.
    if OPA_LOCAL_MODE:
        allowed, reasons = _evaluate_local(user, action, resource)
        user_id = user.get('user_id') or user.get('id')
        if not allowed:
            logger.info(
                "policy_decision",
                extra={"user_id": user_id, "action": action,
                       "allowed": False, "reasons": reasons, "mode": "local"}
            )
        else:
            logger.debug(
                "policy_decision",
                extra={"user_id": user_id, "action": action,
                       "allowed": True, "mode": "local"}
            )
        _cache.put(ck, allowed)
        return allowed

    # OPA sidecar mode: HTTP call.
    try:
        client = await _get_client()
        opa_input = _build_input(user, action, resource)
        resp = await client.post(f"/{OPA_AUTHZ_PATH}", json=opa_input)
        resp.raise_for_status()
        result = resp.json()
        allowed = result.get("result", False)
        _cache.put(ck, allowed)
        user_id = opa_input['input']['user']['user_id']

        if not allowed:
            logger.info(
                "policy_decision",
                extra={"user_id": user_id, "action": action,
                       "allowed": False, "mode": "sidecar"}
            )
        else:
            logger.debug(
                "policy_decision",
                extra={"user_id": user_id, "action": action,
                       "allowed": True, "mode": "sidecar"}
            )

        return allowed

    except httpx.HTTPError as e:
        logger.error(f"OPA request failed: {e}")
        if OPA_FAIL_OPEN:
            logger.warning("OPA unreachable — failing open (ALLOW)")
            return True
        logger.warning("OPA unreachable — failing closed (DENY)")
        return False


async def check_tenant_policy(
    user: Dict[str, Any],
    action: str,
    resource: Dict[str, Any],
) -> bool:
    """Check tenant-scoped policy (includes ownership verification)."""
    if OPA_LOCAL_MODE:
        return await check_policy(user, action, resource)

    try:
        client = await _get_client()
        opa_input = _build_input(user, action, resource)
        resp = await client.post(f"/{OPA_TENANT_PATH}", json=opa_input)
        resp.raise_for_status()
        result = resp.json()
        return result.get("result", False)
    except httpx.HTTPError as e:
        logger.error(f"OPA tenant policy request failed: {e}")
        return not OPA_FAIL_OPEN


async def enforce_policy(
    user: Dict[str, Any],
    action: str,
    resource: Optional[Dict[str, Any]] = None,
) -> None:
    """Enforce policy — raises HTTPException 403 if denied."""
    allowed = await check_policy(user, action, resource)
    if not allowed:
        raise HTTPException(
            status_code=403,
            detail=f"Access denied: insufficient permissions for '{action}'",
        )


async def enforce_tenant_policy(
    user: Dict[str, Any],
    action: str,
    resource: Dict[str, Any],
) -> None:
    """Enforce tenant-scoped policy — raises 403 on denial."""
    allowed = await check_tenant_policy(user, action, resource)
    if not allowed:
        raise HTTPException(
            status_code=403,
            detail=f"Access denied: insufficient permissions for '{action}' on resource",
        )


# ── FastAPI Dependencies ─────────────────────────────────────────


def require_permission(action: str):
    """Create a FastAPI dependency that enforces a specific permission.

    Usage:
        @router.get("/tasks")
        async def list_tasks(user=Depends(require_permission("tasks:read"))):
            ...
    """

    async def _dependency(request: Request) -> Dict[str, Any]:
        # Resolve user from either auth system.
        user = await _resolve_user(request)
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")

        await enforce_policy(user, action)
        return user

    return _dependency


def require_resource_permission(action: str):
    """Create a dependency that enforces permission with resource context.

    The resource context must be set on request.state.policy_resource
    before this dependency runs (e.g. by a path-operation decorator
    or earlier dependency).
    """

    async def _dependency(request: Request) -> Dict[str, Any]:
        user = await _resolve_user(request)
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")

        resource = getattr(request.state, "policy_resource", None)
        await enforce_policy(user, action, resource)
        return user

    return _dependency


async def _resolve_user(request: Request) -> Optional[Dict[str, Any]]:
    """Resolve authenticated user from request using existing auth systems.

    Tries Keycloak auth first, then self-service auth.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None

    token = auth_header[7:]

    # Try self-service / API key auth (handles all token types)
    try:
        from .user_auth import get_current_user as user_auth_get_current_user
        from fastapi.security import HTTPAuthorizationCredentials

        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        user = await user_auth_get_current_user(request, creds)
        if user:
            return user
    except Exception:
        pass

    # Fallback: try Keycloak-only auth
    try:
        from .keycloak_auth import get_current_user as kc_get_current_user
        from fastapi.security import HTTPAuthorizationCredentials

        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        session = await kc_get_current_user(creds)
        if session:
            return {
                "id": session.user_id,
                "user_id": session.user_id,
                "email": session.email,
                "roles": session.roles,
                "tenant_id": session.tenant_id,
                "realm_name": session.realm_name,
            }
    except Exception:
        pass

    return None


# ── OPA Health Check ─────────────────────────────────────────────


async def opa_health() -> Dict[str, Any]:
    """Check OPA sidecar health. Returns status dict."""
    if OPA_LOCAL_MODE:
        data = _load_local_policy_data()
        return {
            "mode": "local",
            "healthy": True,
            "roles_loaded": len(data.get("roles", {})),
        }

    try:
        client = await _get_client()
        resp = await client.get("/health")
        return {
            "mode": "sidecar",
            "healthy": resp.status_code == 200,
            "url": OPA_URL,
        }
    except Exception as e:
        return {
            "mode": "sidecar",
            "healthy": False,
            "url": OPA_URL,
            "error": str(e),
        }


# ── Cleanup ──────────────────────────────────────────────────────


async def close_policy_client() -> None:
    """Close the HTTP client. Call on app shutdown."""
    global _http_client
    if _http_client and not _http_client.is_closed:
        await _http_client.aclose()
        _http_client = None
