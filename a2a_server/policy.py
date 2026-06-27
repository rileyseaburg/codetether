"""OPA Policy Engine Client for A2A Server.

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

    await enforce_policy(
        user,
        "tasks:write",
        resource={
            "type": "task",
            "id": task_id,
            "owner_id": owner,
            "tenant_id": tid,
        },
    )
"""

import functools
import hashlib
import json
import logging
import os
import time

from pathlib import Path
from typing import Any

import httpx

from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials

from a2a_server.provenance import verify_provenance


logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────

OPA_URL = os.environ.get('OPA_URL', 'http://localhost:8181')
OPA_AUTHZ_PATH = os.environ.get('OPA_AUTHZ_PATH', 'v1/data/authz/allow')
OPA_TENANT_PATH = os.environ.get('OPA_TENANT_PATH', 'v1/data/tenants/allow')
OPA_TIMEOUT = float(os.environ.get('OPA_TIMEOUT', '2.0'))

# When OPA is unreachable, fail open (allow) or closed (deny).
# Default: closed (deny) for security.
OPA_FAIL_OPEN = os.environ.get('OPA_FAIL_OPEN', 'false').lower() == 'true'

# Decision cache TTL in seconds (0 = disabled).
OPA_CACHE_TTL = float(os.environ.get('OPA_CACHE_TTL', '5.0'))

# For local/dev mode: evaluate policies in-process without OPA sidecar.
OPA_LOCAL_MODE = os.environ.get('OPA_LOCAL_MODE', 'false').lower() == 'true'

# Master toggle: set to "false" to disable all policy enforcement.
OPA_ENABLED = os.environ.get('OPA_ENABLED', 'true').lower() == 'true'

# Path to policies directory (for local mode and bundle building).
POLICIES_DIR = Path(__file__).parent.parent / 'policies'

# When the decision cache grows past this size, evict entries older than the
# TTL. Bound keeps memory predictable in long-running OPA-sidecar deployments.
_DECISION_CACHE_EVICT_THRESHOLD = 10000

# A permission string has the form "resource:action" — exactly two parts.
_PERMISSION_PARTS = 2

# HTTP 200 OK, used in OPA health checks.
_HTTP_OK = 200


# ── Decision cache ───────────────────────────────────────────────


class _DecisionCache:
    """Simple TTL cache for OPA decisions. Thread-safe via GIL."""

    def __init__(self, ttl: float):
        self._ttl = ttl
        self._store: dict[str, tuple] = {}  # key → (result, timestamp)

    def get(self, key: str) -> bool | None:
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
        if len(self._store) > _DECISION_CACHE_EVICT_THRESHOLD:
            cutoff = time.monotonic() - self._ttl
            self._store = {
                k: v for k, v in self._store.items() if v[1] > cutoff
            }

    def clear(self) -> None:
        """Clear all cached decisions."""
        self._store.clear()


_cache = _DecisionCache(OPA_CACHE_TTL)

# ── Local policy data (for local mode) ──────────────────────────


@functools.lru_cache(maxsize=1)
def _load_local_policy_data() -> dict[str, Any]:
    """Load data.json for local policy evaluation.

    Memoized via lru_cache so the file is only read on first call. Use
    ``reload_local_policy_data()`` to invalidate after editing policies.
    """
    data_file = POLICIES_DIR / 'data.json'
    if data_file.exists():
        with data_file.open() as f:
            return json.load(f)
    logger.warning(f'Policy data file not found: {data_file}')
    return {'roles': {}, 'public_endpoints': []}


def reload_local_policy_data() -> dict[str, Any]:
    """Force reload of local policy data from disk and clear decision cache."""
    _load_local_policy_data.cache_clear()
    _cache.clear()
    return _load_local_policy_data()


def _resolve_role_permissions(
    user: dict[str, Any], data: dict[str, Any]
) -> tuple[set, set]:
    """Resolve a user's effective roles and the permissions they grant."""
    effective_roles: set = set()
    for role in _effective_roles(user):
        role_def = data.get('roles', {}).get(role)
        if not role_def:
            continue
        parent = role_def.get('inherits')
        effective_roles.add(parent if parent else role)

    role_permissions: set = set()
    for role in effective_roles:
        role_def = data.get('roles', {}).get(role)
        if role_def:
            role_permissions.update(role_def.get('permissions', []))
    return effective_roles, role_permissions


def _api_key_scope_allows(user: dict[str, Any], action: str) -> bool:
    """Return True if the API-key scopes permit the action (incl. wildcard)."""
    scopes = user.get('api_key_scopes') or user.get('scopes', [])
    if action in scopes:
        return True
    parts = action.split(':')
    if len(parts) == _PERMISSION_PARTS:
        return f'{parts[0]}:*' in scopes
    return False


def _evaluate_local(
    user: dict[str, Any],
    action: str,
    resource: dict[str, Any] | None = None,
) -> tuple:
    """Evaluate authorization locally without OPA sidecar.

    Returns (allowed: bool, reasons: list[str]).
    """
    data = _load_local_policy_data()
    resource = resource or {}
    reasons: list[str] = []

    # Public endpoints.
    if action in data.get('public_endpoints', []):
        return True, []

    # Resolve effective roles and the permissions they grant.
    effective_roles, role_permissions = _resolve_role_permissions(user, data)

    # Check role-based access.
    if action not in role_permissions:
        reasons.append('no matching role permission')
        return False, reasons

    # API key scope enforcement.
    if _detect_auth_source(user) == 'api_key' and not _api_key_scope_allows(
        user, action
    ):
        reasons.append('api key scope does not permit action')
        return False, reasons

    # Tenant isolation.
    resource_tenant = resource.get('tenant_id')
    user_tenant = user.get('tenant_id')
    is_admin = bool(effective_roles & {'admin'})

    if (
        resource_tenant
        and user_tenant
        and resource_tenant != user_tenant
        and not is_admin
    ):
        reasons.append('cross-tenant access denied')
        return False, reasons

    # Agent Provenance Framework checks. Legacy users without provenance remain
    # compatible; once provenance claims are present, failures deny the action.
    provenance = user.get('provenance') or user.get('agent_provenance')
    decision = verify_provenance(provenance, action, resource)
    if provenance and not decision.allowed_by_provenance:
        reasons.extend(decision.failures)
        return False, reasons

    return True, reasons


# ── OPA HTTP client ──────────────────────────────────────────────

# Persistent client for connection pooling.
_http_client: httpx.AsyncClient | None = None


async def _get_client() -> httpx.AsyncClient:
    global _http_client  # noqa: PLW0603 - module-level pooled client singleton
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            base_url=OPA_URL,
            timeout=OPA_TIMEOUT,
        )
    return _http_client


# Authenticated users with no explicit role assignment get "editor" by default.
# This covers self-service registrations and API key users who sign up via
# /v1/users/register.  Keycloak users get roles from the IdP token.
_DEFAULT_SELF_SERVICE_ROLE = os.environ.get('DEFAULT_USER_ROLE', 'editor')


# Keycloak commonly adds realm roles such as default-roles-<realm>,
# offline_access, and uma_authorization to every authenticated user.  Those are
# identity-provider plumbing roles, not application RBAC assignments.  A
# tenant-scoped Keycloak dashboard session with only those built-ins should get
# the same safe default read/write app role as self-service users so DB-backed
# dashboard panes do not 403 just because no app role has been explicitly
# minted into the token yet.  Keycloak users with no tenant remain denied.
_DEFAULT_KEYCLOAK_TENANT_ROLE = os.environ.get(
    'DEFAULT_KEYCLOAK_TENANT_ROLE', _DEFAULT_SELF_SERVICE_ROLE
)
_DEFAULT_KEYCLOAK_REALM_ROLES = {
    'offline_access',
    'uma_authorization',
    # Keycloak account-console client roles are identity/profile plumbing, not
    # CodeTether app RBAC. Treating them as app roles prevents tenant-scoped
    # dashboard users from receiving the safe default role and causes 403s on
    # DB-backed panes such as /v1/agent/workflows/github-app.
    'manage-account',
    'manage-account-links',
    'view-profile',
}


def _is_default_keycloak_realm_role(role: object) -> bool:
    """Return True for Keycloak built-in realm roles that are not app RBAC."""
    if not isinstance(role, str):
        return False
    return role in _DEFAULT_KEYCLOAK_REALM_ROLES or role.startswith(
        'default-roles-'
    )


def _known_policy_roles() -> set[str]:
    """Return the app RBAC roles known to the policy data file.

    Keycloak access tokens flatten realm roles and client roles into one list in
    user_auth._extract_keycloak_roles().  Client/account-console roles such as
    ``manage-consent`` or ``view-applications`` are real Keycloak roles but are
    not CodeTether RBAC roles.  If we treat those unknown roles as app roles, a
    tenant-scoped dashboard session never receives the safe default role and
    read-only panes such as /v1/agent/workflows/github-app 403 before the
    tenant-scoped query can run.

    Some tenant images run in OPA_LOCAL_MODE without bundling
    policies/data.json.
    Keep explicit application RBAC roles authoritative in that case instead of
    downgrading every tenant Keycloak user to the default editor role.
    """
    roles = (_load_local_policy_data().get('roles') or {}).keys()
    if roles:
        return set(roles)
    return {'admin', 'a2a-admin', 'operator', 'editor', 'viewer'}


def _effective_roles(user: dict[str, Any]) -> list:
    """Return app RBAC roles, applying safe defaults for dashboard sessions."""
    roles = user.get('roles', [])
    auth_source = _detect_auth_source(user)

    if roles:
        if auth_source == 'keycloak':
            known_roles = _known_policy_roles()
            app_roles = [
                role
                for role in roles
                if isinstance(role, str)
                and role in known_roles
                and not _is_default_keycloak_realm_role(role)
            ]
            if app_roles:
                return app_roles
            if user.get('tenant_id'):
                return [_DEFAULT_KEYCLOAK_TENANT_ROLE]
            return []
        return roles

    if auth_source in ('self-service', 'api_key'):
        return [_DEFAULT_SELF_SERVICE_ROLE]
    return roles


def _build_input(
    user: dict[str, Any],
    action: str,
    resource: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the OPA input document from user context and request."""
    return {
        'input': {
            'user': {
                'user_id': user.get('user_id')
                or user.get('id')
                or user.get('sub', ''),
                'roles': _effective_roles(user),
                'tenant_id': user.get('tenant_id'),
                'scopes': user.get('api_key_scopes') or user.get('scopes', []),
                'auth_source': _detect_auth_source(user),
            },
            'action': action,
            'resource': resource or {},
            'provenance': user.get('provenance')
            or user.get('agent_provenance')
            or {},
        }
    }


def _detect_auth_source(user: dict[str, Any]) -> str:
    """Determine how the user authenticated."""
    explicit = user.get('auth_source')
    if explicit:
        return explicit
    if user.get('spiffe_id'):
        return 'spiffe'
    if user.get('api_key_scopes') is not None:
        return 'api_key'
    if (
        user.get('type') == 'keycloak'
        or user.get('keycloak_sub')
        or user.get('realm_name')
    ):
        return 'keycloak'
    return 'self-service'


def _cache_key(
    user: dict[str, Any], action: str, resource: dict[str, Any] | None
) -> str:
    """Build a deterministic cache key."""
    uid = user.get('user_id') or user.get('id') or user.get('sub', '')
    tid = user.get('tenant_id') or ''
    rid = ''
    rtid = ''
    if resource:
        rid = resource.get('id', '')
        rtid = resource.get('tenant_id', '')
    provenance = user.get('provenance') or user.get('agent_provenance') or {}
    ap_session = (
        provenance.get('ap_session', {}) if isinstance(provenance, dict) else {}
    )
    pjti = (
        ap_session.get('parent_jti', '') if isinstance(ap_session, dict) else ''
    )
    turn = ap_session.get('turn', '') if isinstance(ap_session, dict) else ''
    provenance_hash = ''
    if OPA_CACHE_TTL > 0 and isinstance(provenance, dict) and provenance:
        serialized = json.dumps(
            provenance, sort_keys=True, separators=(',', ':'), default=str
        )
        provenance_hash = hashlib.sha256(serialized.encode('utf-8')).hexdigest()
    return f'{uid}:{action}:{tid}:{rid}:{rtid}:{pjti}:{turn}:{provenance_hash}'


# ── Public API ───────────────────────────────────────────────────


async def check_policy(
    user: dict[str, Any],
    action: str,
    resource: dict[str, Any] | None = None,
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
                'policy_decision',
                extra={
                    'user_id': user_id,
                    'action': action,
                    'allowed': False,
                    'reasons': reasons,
                    'mode': 'local',
                },
            )
        else:
            logger.debug(
                'policy_decision',
                extra={
                    'user_id': user_id,
                    'action': action,
                    'allowed': True,
                    'mode': 'local',
                },
            )
        _cache.put(ck, allowed)
        return allowed

    # OPA sidecar mode: HTTP call.
    try:
        client = await _get_client()
        opa_input = _build_input(user, action, resource)
        resp = await client.post(f'/{OPA_AUTHZ_PATH}', json=opa_input)
        resp.raise_for_status()
        result = resp.json()
        allowed = result.get('result', False)
        _cache.put(ck, allowed)
        user_id = opa_input['input']['user']['user_id']

        if not allowed:
            logger.info(
                'policy_decision',
                extra={
                    'user_id': user_id,
                    'action': action,
                    'allowed': False,
                    'mode': 'sidecar',
                },
            )
        else:
            logger.debug(
                'policy_decision',
                extra={
                    'user_id': user_id,
                    'action': action,
                    'allowed': True,
                    'mode': 'sidecar',
                },
            )

        return allowed

    except httpx.HTTPError as e:
        logger.error(f'OPA request failed: {e}')
        if OPA_FAIL_OPEN:
            logger.warning('OPA unreachable — failing open (ALLOW)')
            return True
        logger.warning('OPA unreachable — failing closed (DENY)')
        return False


async def check_tenant_policy(
    user: dict[str, Any],
    action: str,
    resource: dict[str, Any],
) -> bool:
    """Check tenant-scoped policy (includes ownership verification)."""
    if OPA_LOCAL_MODE:
        return await check_policy(user, action, resource)

    try:
        client = await _get_client()
        opa_input = _build_input(user, action, resource)
        resp = await client.post(f'/{OPA_TENANT_PATH}', json=opa_input)
        resp.raise_for_status()
        result = resp.json()
        return result.get('result', False)
    except httpx.HTTPError as e:
        logger.error(f'OPA tenant policy request failed: {e}')
        return not OPA_FAIL_OPEN


async def enforce_policy(
    user: dict[str, Any],
    action: str,
    resource: dict[str, Any] | None = None,
) -> None:
    """Enforce policy — raises HTTPException 403 if denied."""
    allowed = await check_policy(user, action, resource)
    if not allowed:
        raise HTTPException(
            status_code=403,
            detail=f"Access denied: insufficient permissions for '{action}'",
        )


async def enforce_tenant_policy(
    user: dict[str, Any],
    action: str,
    resource: dict[str, Any],
) -> None:
    """Enforce tenant-scoped policy — raises 403 on denial."""
    allowed = await check_tenant_policy(user, action, resource)
    if not allowed:
        raise HTTPException(
            status_code=403,
            detail=(
                f"Access denied: insufficient permissions for "
                f"'{action}' on resource"
            ),
        )


# ── FastAPI Dependencies ─────────────────────────────────────────


def require_permission(action: str):
    """Create a FastAPI dependency that enforces a specific permission.

    Usage:
        @router.get("/tasks")
        async def list_tasks(user=Depends(require_permission("tasks:read"))):
            ...
    """

    async def _dependency(request: Request) -> dict[str, Any]:
        # Resolve user from either auth system.
        user = await _resolve_user(request)
        if not user:
            raise HTTPException(
                status_code=401, detail='Authentication required'
            )

        await enforce_policy(user, action)
        return user

    return _dependency


def require_resource_permission(action: str):
    """Create a dependency that enforces permission with resource context.

    The resource context must be set on request.state.policy_resource
    before this dependency runs (e.g. by a path-operation decorator
    or earlier dependency).
    """

    async def _dependency(request: Request) -> dict[str, Any]:
        user = await _resolve_user(request)
        if not user:
            raise HTTPException(
                status_code=401, detail='Authentication required'
            )

        resource = getattr(request.state, 'policy_resource', None)
        await enforce_policy(user, action, resource)
        return user

    return _dependency


async def _resolve_user(request: Request) -> dict[str, Any] | None:
    """Resolve authenticated user from request using existing auth systems.

    Tries Keycloak auth first, then self-service auth.
    Supports Bearer token from Authorization header, with query param
    fallback (access_token) for SSE/EventSource connections that cannot
    set custom headers.
    """
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header[7:]
    else:
        # Fallback: check query param for SSE/EventSource connections
        token = request.query_params.get('access_token')

    if not token:
        return None

    # Try self-service / API key auth (handles all token types)
    try:
        from a2a_server.user_auth import (  # noqa: PLC0415 - deferred: avoids import cycle
            get_current_user as user_auth_get_current_user,
        )

        creds = HTTPAuthorizationCredentials(scheme='Bearer', credentials=token)
        user = await user_auth_get_current_user(request, creds)
        if user:
            return user
    except Exception:
        pass

    # Otherwise, try Keycloak-only auth
    try:
        from a2a_server.keycloak_auth import (  # noqa: PLC0415 - deferred: avoids import cycle
            get_current_user as kc_get_current_user,
        )

        creds = HTTPAuthorizationCredentials(scheme='Bearer', credentials=token)
        session = await kc_get_current_user(creds)
        if session:
            return {
                'id': session.user_id,
                'user_id': session.user_id,
                'email': session.email,
                'roles': session.roles,
                'tenant_id': session.tenant_id,
                'type': 'keycloak',
                'keycloak_sub': session.user_id,
                'realm_name': session.realm_name,
            }
    except Exception:
        pass

    return None


# ── OPA Health Check ─────────────────────────────────────────────


async def opa_health() -> dict[str, Any]:
    """Check OPA sidecar health. Returns status dict."""
    if OPA_LOCAL_MODE:
        data = _load_local_policy_data()
        return {
            'mode': 'local',
            'healthy': True,
            'roles_loaded': len(data.get('roles', {})),
        }

    try:
        client = await _get_client()
        resp = await client.get('/health')
        return {
            'mode': 'sidecar',
            'healthy': resp.status_code == _HTTP_OK,
            'url': OPA_URL,
        }
    except Exception as e:
        return {
            'mode': 'sidecar',
            'healthy': False,
            'url': OPA_URL,
            'error': str(e),
        }


# ── Cleanup ──────────────────────────────────────────────────────


async def close_policy_client() -> None:
    """Close the HTTP client. Call on app shutdown."""
    global _http_client  # noqa: PLW0603 - module-level pooled client singleton
    if _http_client and not _http_client.is_closed:
        await _http_client.aclose()
        _http_client = None
