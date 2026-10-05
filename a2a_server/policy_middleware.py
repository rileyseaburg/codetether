"""Centralized Authorization Middleware for A2A Server.

Maps HTTP path patterns + methods to OPA permission strings and enforces
authorization via the policy engine. This secures ~120 previously-unprotected
endpoints without modifying individual route signatures.

Endpoints that are intentionally public or already protected by existing
auth dependencies are skipped.
"""

import hmac
import logging
import os
import re

from starlette.middleware.base import (
    BaseHTTPMiddleware,
    RequestResponseEndpoint,
)
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from a2a_server import policy, spiffe_auth
from a2a_server.oauth_provider import www_authenticate_header


logger = logging.getLogger(__name__)

#: Public base URL used in RFC 6750 resource_metadata (same source as
#: oauth_provider's protected-resource metadata).
_SERVER_URL = os.environ.get(
    'MCP_SERVER_URL', 'https://api.codetether.run'
).rstrip('/')

# ── Worker Authentication ────────────────────────────────────────
# Worker infrastructure endpoints (registration, heartbeats, task polling,
# task listing) require either a valid WORKER_AUTH_TOKEN bearer or an
# authenticated platform user. Zero trust: nothing is open by default.
#
# Before this change, an unset WORKER_AUTH_TOKEN left these routes open to
# the internet ("trust cluster-internal traffic"), exposing every task's
# prompt/result and every worker's registration to anonymous callers.
#
# A2A_ALLOW_UNAUTHENTICATED_WORKERS=true restores open access for local dev.
WORKER_AUTH_TOKEN: str | None = os.environ.get('WORKER_AUTH_TOKEN')
_WORKER_PATH = re.compile(
    r'^/v1/agent/(workers(/.*)?|tasks(/|/[^/]+/(output|status|claim|complete|cancel|requeue))?/?)$'
)
#: Worker-path requests that stay public. The marketing chat widget creates
#: tasks anonymously; its metadata is sanitized (see task_metadata_trust).
_PUBLIC_WORKER_ROUTES = frozenset({('/v1/agent/tasks', 'POST')})


def _unauthenticated_workers_allowed() -> bool:
    value = os.environ.get('A2A_ALLOW_UNAUTHENTICATED_WORKERS', '')
    return value.strip().lower() in {'1', 'true', 'yes'}


def _spiffe_only_workers() -> bool:
    """SPIRE-native mode: reject shared WORKER_AUTH_TOKEN bearers.

    Mirrors SPIFFE_ALLOW_TOKEN_LEGACY: once workers present JWT-SVIDs,
    set it to false and the shared-secret path is closed.
    """
    legacy = os.environ.get('SPIFFE_ALLOW_TOKEN_LEGACY', 'true')
    spiffe = os.environ.get('SPIFFE_ENABLED', 'false')
    return spiffe.lower() == 'true' and legacy.lower() != 'true'


def _worker_path_exempt(path: str, method: str) -> bool:
    """Public chat task creation and explicit dev mode skip worker auth."""
    if (path.rstrip('/') or '/', method) in _PUBLIC_WORKER_ROUTES:
        return True
    return _unauthenticated_workers_allowed()


def _worker_auth_required() -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={
            'detail': 'Worker authentication required (set --token on worker)'
        },
        headers={'WWW-Authenticate': 'Bearer'},
    )


def worker_identity_allowed(user: dict) -> bool:
    """Non-SPIFFE users pass through; SPIFFE callers must be allow-listed."""
    if user.get('auth_source') != 'spiffe':
        return True
    return spiffe_auth.is_allowed_worker(str(user.get('spiffe_id') or ''))


# ── Path → Permission Mapping ────────────────────────────────────
#
# Each rule is (path_regex, http_methods, permission_action).
# Rules are evaluated top-to-bottom; first match wins.
# Use None for http_methods to match any method.
#
# Endpoints NOT listed here pass through without middleware-level
# authorization (they may still have their own auth dependencies).

_RULES: list[tuple[str, set | None, str]] = [
    # ── Public / Skip (no auth required) ─────────────────────────
    # These return "" to signal "skip authorization".
    (r'^/health$', None, ''),
    (r'^/\.well-known/', None, ''),
    (r'^/static/', None, ''),
    (r'^/docs', None, ''),
    (r'^/openapi\.json$', None, ''),
    (r'^/redoc', None, ''),
    # Expiring HMAC-signed task transcript links validate in the route handler.
    (r'^/sessions/tasks/[^/]+$', {'GET'}, ''),
    # Auth endpoints — intentionally public
    (r'^/v1/auth/login$', None, ''),
    (r'^/v1/auth/refresh$', None, ''),
    (r'^/v1/auth/logout$', None, ''),
    (r'^/v1/auth/status$', None, ''),
    (r'^/api/auth/', None, ''),  # NextAuth compat — all public
    # OAuth 2.1 endpoints — public by spec
    (r'^/oauth/', None, ''),
    # User auth — public endpoints
    (r'^/v1/users/register$', {'POST'}, ''),
    (r'^/v1/users/login$', {'POST'}, ''),
    (r'^/v1/users/password-reset/', None, ''),
    # Tenant signup — public
    (r'^/v1/tenants/signup$', {'POST'}, ''),
    # Crash reports — agents submit without user auth
    (r'^/v1/crash-reports$', {'POST'}, ''),
    # A2A protocol discovery
    (r'^/a2a/\.well-known/', None, ''),
    # Agent discovery — read-only model/provider listing
    (r'^/v1/agent/models$', {'GET'}, ''),
    (r'^/v1/agent/providers$', {'GET'}, ''),
    # Billing webhooks — Stripe signature verified
    (r'^/v1/webhooks/stripe$', {'POST'}, ''),
    (r'^/v1/webhooks/github$', {'POST'}, ''),
    # Forgejo webhooks and native agent controls verify HMAC signatures.
    (r'^/v1/webhooks/forgejo(?:/agent-control)?$', {'POST'}, ''),
    # ── Already-protected routes (skip to avoid double auth) ─────
    # Billing, admin, tenant (non-signup), user auth (non-public),
    # cronjobs, queue — all have existing Depends(require_*).
    (r'^/v1/billing/', None, ''),
    (r'^/v1/admin/', None, ''),
    (r'^/v1/tenants/', None, ''),  # signup already skipped above
    (r'^/v1/users/', None, ''),  # public endpoints already skipped above
    (r'^/v1/cronjobs', None, ''),
    (r'^/v1/queue/', None, ''),
    # ── Monitor Router (/v1/monitor) ─────────────────────────────
    (r'^/v1/monitor/intervene$', {'POST'}, 'monitor:write'),
    (r'^/v1/monitor/export/', {'GET'}, 'monitor:read'),
    (r'^/v1/monitor', None, 'monitor:read'),
    # ── Agent Router (/v1/agent) ─────────────────────────────────
    # Database admin endpoints
    (r'^/v1/agent/database/codebases/deduplicate$', {'POST'}, 'admin:access'),
    (r'^/v1/agent/database/', None, 'admin:access'),
    (r'^/v1/agent/reaper/', None, 'admin:access'),
    (r'^/v1/agent/vault/status$', {'GET'}, 'api_keys:read'),
    (r'^/v1/agent/vault/', None, 'admin:access'),
    (r'^/v1/agent/tasks/stuck', None, 'admin:access'),
    # API keys (already have soft auth, reinforce with policy)
    (r'^/v1/agent/api-keys$', {'GET'}, 'api_keys:read'),
    (r'^/v1/agent/api-keys$', {'POST'}, 'api_keys:write'),
    (r'^/v1/agent/api-keys/sync$', {'GET'}, 'api_keys:read'),
    (r'^/v1/agent/api-keys/test$', {'POST'}, 'api_keys:write'),
    (r'^/v1/agent/api-keys/', {'DELETE'}, 'api_keys:delete'),
    # GitHub App workflow pane is tenant-scoped by the route handler. Tenant
    # deployments commonly run with local auth defaults, so skip OPA here and
    # let the handler apply tenant scoping instead of surfacing dashboard 403s.
    (r'^/v1/agent/workflows/github-app$', {'GET'}, ''),
    # Worker management — registration, heartbeat, task-polling, and claiming
    # are internal infrastructure (workers run on trusted nodes), so skip auth.
    (r'^/v1/agent/workers/register$', {'POST'}, ''),
    (r'^/v1/agent/workers/[^/]+/unregister$', {'POST'}, ''),
    (r'^/v1/agent/workers/[^/]+/heartbeat$', {'POST'}, ''),
    (r'^/v1/agent/tasks$', {'GET'}, ''),  # worker task polling (status=pending)
    (r'^/v1/agent/workers/[^/]+/profile$', {'POST'}, 'workers:write'),
    (r'^/v1/agent/workers$', {'GET'}, ''),
    (r'^/v1/agent/workers/', {'GET'}, ''),
    # Workspace list includes git_auth config and every registered path;
    # it is dashboard data, not worker infrastructure.
    (r'^/v1/agent/workspaces/list$', {'GET'}, 'codebases:read'),
    # Worker profiles
    (r'^/v1/agent/worker-profiles$', {'POST'}, 'workers:write'),
    (r'^/v1/agent/worker-profiles$', {'GET'}, 'workers:read'),
    (r'^/v1/agent/worker-profiles/', {'GET'}, 'workers:read'),
    (r'^/v1/agent/worker-profiles/', {'PATCH'}, 'workers:write'),
    (r'^/v1/agent/worker-profiles/', {'DELETE'}, 'workers:delete'),
    # Codebase mutations
    (r'^/v1/agent/codebases$', {'POST'}, 'codebases:write'),
    (r'^/v1/agent/codebases/[^/]+/trigger$', {'POST'}, 'codebases:write'),
    (r'^/v1/agent/codebases/[^/]+/message$', {'POST'}, 'codebases:write'),
    (r'^/v1/agent/codebases/[^/]+/interrupt$', {'POST'}, 'codebases:write'),
    (r'^/v1/agent/codebases/[^/]+/stop$', {'POST'}, 'codebases:write'),
    (r'^/v1/agent/codebases/[^/]+/upload$', {'POST'}, 'codebases:write'),
    (r'^/v1/agent/codebases/[^/]+/sync$', {'POST'}, 'codebases:write'),
    (r'^/v1/agent/codebases/[^/]+/watch/start$', {'POST'}, 'codebases:write'),
    (r'^/v1/agent/codebases/[^/]+/watch/stop$', {'POST'}, 'codebases:write'),
    (r'^/v1/agent/codebases/[^/]+$', {'DELETE'}, 'codebases:delete'),
    # Session mutations (before codebase GET catch-all)
    (
        r'^/v1/agent/codebases/[^/]+/sessions/[^/]+/ingest$',
        {'POST'},
        'sessions:write',
    ),
    (r'^/v1/agent/codebases/[^/]+/sessions/sync$', {'POST'}, 'sessions:write'),
    (
        r'^/v1/agent/codebases/[^/]+/sessions/[^/]+/resume$',
        {'POST'},
        'sessions:write',
    ),
    (r'^/v1/agent/workspaces/[^/]+/session-access$', {'POST'}, 'sessions:write'),
    (r'^/v1/agent/codebases/[^/]+/sessions', {'GET'}, 'sessions:read'),
    (r'^/v1/agent/runtime/sessions/[^/]+/messages$', {'GET'}, 'sessions:read'),
    (r'^/v1/agent/runtime/sessions/[^/]+/parts$', {'GET'}, 'sessions:read'),
    (r'^/v1/agent/runtime/sessions/', {'GET'}, 'sessions:read'),
    (r'^/v1/agent/sessions/[^/]+/worker-status$', {'GET'}, 'sessions:read'),
    # Public marketing chat creates short-lived anonymous support tasks and
    # polls the returned task id. It cannot rely on app RBAC roles, but it also
    # does not expose task listing or mutation beyond the random id it receives.
    (r'^/v1/agent/tasks$', {'POST'}, ''),
    (r'^/v1/agent/codebases/[^/]+/tasks$', {'POST'}, 'tasks:write'),
    (r'^/v1/agent/tasks/[^/]+/cancel$', {'POST'}, 'tasks:write'),
    (r'^/v1/agent/tasks/[^/]+/status$', {'PUT'}, 'tasks:write'),
    (r'^/v1/agent/tasks/[^/]+/output$', {'POST'}, 'tasks:write'),
    (r'^/v1/agent/tasks/[^/]+/requeue$', {'POST'}, 'tasks:write'),
    # Codebase/task GET catch-all (AFTER specific session/task sub-paths)
    (r'^/v1/agent/codebases/[^/]+/tasks$', {'GET'}, 'tasks:read'),
    (r'^/v1/agent/codebases', {'GET'}, 'codebases:read'),
    # Public marketing chat polls the unguessable task id it was just given.
    # Listing remains skipped separately above only for worker polling.
    (r'^/v1/agent/tasks/[^/]+$', {'GET'}, ''),
    # Task reads
    (r'^/v1/agent/tasks', {'GET'}, 'tasks:read'),
    # Agent info reads (status, runtime, models, providers)
    (r'^/v1/agent/status$', {'GET'}, 'agent:read'),
    (r'^/v1/agent/runtime/', {'GET'}, 'agent:read'),
    (r'^/v1/agent/models$', {'GET'}, 'agent:read'),
    (r'^/v1/agent/providers$', {'GET'}, 'agent:read'),
    # ── Auth Router — protected user endpoints ───────────────────
    (r'^/v1/auth/session$', {'GET'}, 'sessions:read'),
    (r'^/v1/auth/sync$', {'GET'}, 'sessions:read'),
    (r'^/v1/auth/user/[^/]+/codebases$', {'GET'}, 'codebases:read'),
    (r'^/v1/auth/user/[^/]+/codebases$', {'POST'}, 'codebases:write'),
    (r'^/v1/auth/user/[^/]+/codebases/', {'DELETE'}, 'codebases:delete'),
    (r'^/v1/auth/user/[^/]+/agent-sessions$', {'GET'}, 'sessions:read'),
    (r'^/v1/auth/user/[^/]+/agent-sessions$', {'POST'}, 'sessions:write'),
    (r'^/v1/auth/agent-sessions/', {'GET'}, 'sessions:read'),
    (r'^/v1/auth/agent-sessions/', {'DELETE'}, 'sessions:delete'),
    # ── Voice Router (/v1/voice) ─────────────────────────────────
    (r'^/v1/voice/sessions$', {'POST'}, 'voice:write'),
    (r'^/v1/voice/sessions/[^/]+$', {'DELETE'}, 'voice:delete'),
    (r'^/v1/voice/', {'GET'}, 'voice:read'),
    # ── Ralph Router (/v1/ralph) ─────────────────────────────────
    (r'^/v1/ralph/runs$', {'POST'}, 'ralph:write'),
    (r'^/v1/ralph/recover$', {'POST'}, 'ralph:write'),
    (r'^/v1/ralph/runs/[^/]+/cancel$', {'POST'}, 'ralph:write'),
    (r'^/v1/ralph/runs/[^/]+$', {'DELETE'}, 'ralph:delete'),
    (r'^/v1/ralph/chat$', {'POST'}, 'ralph:write'),
    (r'^/v1/ralph/', {'GET'}, 'ralph:read'),
    # ── Proactive Router (/v1/proactive) ──────────────────────────
    (r'^/v1/proactive/rules$', {'POST'}, 'proactive:write'),
    (r'^/v1/proactive/rules/[^/]+$', {'PUT'}, 'proactive:write'),
    (r'^/v1/proactive/rules/[^/]+$', {'DELETE'}, 'proactive:delete'),
    (r'^/v1/proactive/rules/[^/]+/trigger$', {'POST'}, 'proactive:write'),
    (r'^/v1/proactive/health-checks$', {'POST'}, 'proactive:write'),
    (r'^/v1/proactive/health-checks/[^/]+$', {'PUT'}, 'proactive:write'),
    (r'^/v1/proactive/health-checks/[^/]+$', {'DELETE'}, 'proactive:delete'),
    (r'^/v1/proactive/loops$', {'POST'}, 'proactive:write'),
    (r'^/v1/proactive/loops/[^/]+$', {'PUT'}, 'proactive:write'),
    (r'^/v1/proactive/loops/[^/]+$', {'DELETE'}, 'proactive:delete'),
    (r'^/v1/proactive/decisions', {'GET'}, 'decisions:read'),
    (r'^/v1/proactive/', {'GET'}, 'proactive:read'),
    # ── Email Routers (/v1/email) ────────────────────────────────
    # Inbound webhook — should verify signature, but at minimum needs auth
    (r'^/v1/email/inbound$', {'POST'}, 'email:write'),
    # All other email endpoints are admin/debug
    (r'^/v1/email/', None, 'email:admin'),
    # ── Analytics Router (/v1/analytics) ─────────────────────────
    # Client-side tracking endpoints — require basic auth
    (r'^/v1/analytics/track$', {'POST'}, 'analytics:write'),
    (r'^/v1/analytics/identify$', {'POST'}, 'analytics:write'),
    (r'^/v1/analytics/page$', {'POST'}, 'analytics:write'),
    # Admin analytics endpoints
    (r'^/v1/analytics/', None, 'analytics:admin'),
    # ── MCP Router (/mcp) ────────────────────────────────────────
    # Zero trust: MCP exposes task creation, messaging, and codebase deletion.
    # It was previously skipped ("internal protocol") and reachable
    # anonymously from the internet. Discovery stays public (MCP spec);
    # everything else needs an authenticated identity with mcp scope.
    (r'^/mcp/?$', {'GET'}, ''),
    (r'^/mcp/v1/tools$', {'GET'}, 'mcp:read'),
    (r'^/mcp/v1/tasks', {'GET'}, 'mcp:read'),
    (r'^/mcp', None, 'mcp:write'),
    # ── Token Billing Router (/v1/token-billing) ─────────────────
    (r'^/v1/token-billing/budgets', {'POST', 'PUT', 'DELETE'}, 'billing:write'),
    (r'^/v1/token-billing/pricing', {'POST', 'PUT', 'DELETE'}, 'billing:write'),
    (r'^/v1/token-billing/', None, 'billing:read'),
    # ── Worker SSE (/v1/worker) — has its own token auth ─────────
    (r'^/v1/worker/', None, ''),
    # ── A2A Protocol (/a2a) ──────────────────────────────────────
    # Zero trust: A2A message/send creates and queues real agent work. The
    # routes were skipped ("optional auth") and ran work for anonymous
    # callers. Discovery (agent card) stays public per the A2A spec.
    (r'^/a2a/card$', {'GET'}, ''),
    (r'^/a2a/rest/tasks/', {'GET'}, 'tasks:read'),
    (r'^/a2a/', None, 'tasks:execute'),
    # ── Server inline routes ─────────────────────────────────────
    (r'^/agents$', {'GET'}, 'agent:read'),
    (r'^/v1/livekit/token$', {'POST'}, ''),  # has its own auth
    (r'^/v1/a2a$', {'POST'}, 'tasks:execute'),  # A2A JSON-RPC
    (r'^/$', {'POST'}, 'tasks:execute'),  # A2A JSON-RPC root
]

# Pre-compile regexes for performance.
_COMPILED_RULES = [
    (re.compile(pattern), methods, perm) for pattern, methods, perm in _RULES
]


def _match_permission(path: str, method: str) -> str | None:
    """Find the required permission for a path + method.

    Returns:
        - permission string if auth is required
        - "" (empty string) if the route should be skipped
        - None if no rule matches (pass through)
    """
    for regex, methods, perm in _COMPILED_RULES:
        if regex.search(path) and (methods is None or method in methods):
            return perm
    return None


def _authentication_required(permission: str) -> JSONResponse:
    """401 with an RFC 9728 / MCP-spec ``WWW-Authenticate`` challenge."""
    return JSONResponse(
        status_code=401,
        content={'detail': 'Authentication required'},
        headers={'WWW-Authenticate': www_authenticate_header(scope=permission)},
    )


def _insufficient_scope(permission: str) -> JSONResponse:
    """403 with an RFC 6750 ``insufficient_scope`` challenge."""
    resource_metadata = f'{_SERVER_URL}/.well-known/oauth-protected-resource'
    return JSONResponse(
        status_code=403,
        content={
            'detail': (
                f"Access denied: insufficient permissions for '{permission}'"
            )
        },
        headers={
            'WWW-Authenticate': (
                f'Bearer error="insufficient_scope", '
                f'scope="{permission}", '
                f'resource_metadata="{resource_metadata}"'
            )
        },
    )


class PolicyAuthorizationMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that enforces OPA policies on matched routes."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Authenticate, then authorize the request against its route rule."""
        if not policy.OPA_ENABLED:
            return await call_next(request)

        path = request.url.path
        method = request.method
        permission = _match_permission(path, method)
        skip = permission is None or permission == ''

        # Worker infrastructure paths: zero trust, never open by default.
        # Accept a valid worker token or an allow-listed identity.
        # Only the public chat POST and an explicit dev opt-in bypass this.
        if _WORKER_PATH.search(path) and not _worker_path_exempt(path, method):
            verdict = await self._authorize_worker(request, path)
            if verdict is not None:
                return verdict
            if skip or request.state.worker_token:
                return await call_next(request)

        if not skip:
            verdict = await self._authorize_user(request, permission)
            if verdict is not None:
                return verdict
        return await call_next(request)

    async def _authorize_user(
        self, request: Request, permission: str
    ) -> JSONResponse | None:
        """Resolve the caller and check ``permission``; None means allowed."""
        user = await self._resolve_user(request)
        if user is None:
            return _authentication_required(permission)
        if not await policy.check_policy(user, permission):
            logger.warning(
                'policy_middleware_denied',
                extra={
                    'user_id': user.get('user_id') or user.get('id'),
                    'action': permission,
                    'path': request.url.path,
                    'method': request.method,
                },
            )
            return _insufficient_scope(permission)
        request.state.policy_user = user
        return None

    async def _authorize_worker(
        self, request: Request, path: str
    ) -> JSONResponse | None:
        """Gate a worker-path request; return a rejection or None to allow.

        Sets ``request.state.worker_token`` when a shared worker token
        authenticated the call (legacy path, closed in SPIRE-native mode).
        """
        request.state.worker_token = bool(
            WORKER_AUTH_TOKEN
            and not _spiffe_only_workers()
            and self._check_worker_token(request)
        )
        if request.state.worker_token:
            return None
        user = await self._resolve_user(request)
        if user is None:
            return _worker_auth_required()
        if not worker_identity_allowed(user):
            logger.warning(
                'SPIFFE identity %s not allowed on worker path %s',
                user.get('spiffe_id'),
                path,
            )
            return JSONResponse(
                status_code=403,
                content={'detail': 'Workload not authorized as worker'},
            )
        request.state.policy_user = user
        return None

    async def _resolve_user(self, request: Request) -> dict | None:
        """Resolve authenticated user from the request."""
        return await policy._resolve_user(request)  # noqa: SLF001 - shared

    @staticmethod
    def _check_worker_token(request: Request) -> bool:
        """Validate a worker Bearer token against WORKER_AUTH_TOKEN."""
        auth = request.headers.get('authorization', '')
        if not auth.startswith('Bearer '):
            return False
        token = auth[7:]
        return hmac.compare_digest(token, WORKER_AUTH_TOKEN)
, {'POST'}, 'sessions:write'),
    # Session reads
    (r'^/v1/agent/codebases/[^/]+/sessions', {'GET'}, 'sessions:read'),
    (r'^/v1/agent/runtime/sessions/[^/]+/messages$', {'GET'}, 'sessions:read'),
    (r'^/v1/agent/runtime/sessions/[^/]+/parts$', {'GET'}, 'sessions:read'),
    (r'^/v1/agent/runtime/sessions/', {'GET'}, 'sessions:read'),
    (r'^/v1/agent/sessions/[^/]+/worker-status$', {'GET'}, 'sessions:read'),
    # Public marketing chat creates short-lived anonymous support tasks and
    # polls the returned task id. It cannot rely on app RBAC roles, but it also
    # does not expose task listing or mutation beyond the random id it receives.
    (r'^/v1/agent/tasks$', {'POST'}, ''),
    (r'^/v1/agent/codebases/[^/]+/tasks$', {'POST'}, 'tasks:write'),
    (r'^/v1/agent/tasks/[^/]+/cancel$', {'POST'}, 'tasks:write'),
    (r'^/v1/agent/tasks/[^/]+/status$', {'PUT'}, 'tasks:write'),
    (r'^/v1/agent/tasks/[^/]+/output$', {'POST'}, 'tasks:write'),
    (r'^/v1/agent/tasks/[^/]+/requeue$', {'POST'}, 'tasks:write'),
    # Codebase/task GET catch-all (AFTER specific session/task sub-paths)
    (r'^/v1/agent/codebases/[^/]+/tasks$', {'GET'}, 'tasks:read'),
    (r'^/v1/agent/codebases', {'GET'}, 'codebases:read'),
    # Public marketing chat polls the unguessable task id it was just given.
    # Listing remains skipped separately above only for worker polling.
    (r'^/v1/agent/tasks/[^/]+$', {'GET'}, ''),
    # Task reads
    (r'^/v1/agent/tasks', {'GET'}, 'tasks:read'),
    # Agent info reads (status, runtime, models, providers)
    (r'^/v1/agent/status$', {'GET'}, 'agent:read'),
    (r'^/v1/agent/runtime/', {'GET'}, 'agent:read'),
    (r'^/v1/agent/models$', {'GET'}, 'agent:read'),
    (r'^/v1/agent/providers$', {'GET'}, 'agent:read'),
    # ── Auth Router — protected user endpoints ───────────────────
    (r'^/v1/auth/session$', {'GET'}, 'sessions:read'),
    (r'^/v1/auth/sync$', {'GET'}, 'sessions:read'),
    (r'^/v1/auth/user/[^/]+/codebases$', {'GET'}, 'codebases:read'),
    (r'^/v1/auth/user/[^/]+/codebases$', {'POST'}, 'codebases:write'),
    (r'^/v1/auth/user/[^/]+/codebases/', {'DELETE'}, 'codebases:delete'),
    (r'^/v1/auth/user/[^/]+/agent-sessions$', {'GET'}, 'sessions:read'),
    (r'^/v1/auth/user/[^/]+/agent-sessions$', {'POST'}, 'sessions:write'),
    (r'^/v1/auth/agent-sessions/', {'GET'}, 'sessions:read'),
    (r'^/v1/auth/agent-sessions/', {'DELETE'}, 'sessions:delete'),
    # ── Voice Router (/v1/voice) ─────────────────────────────────
    (r'^/v1/voice/sessions$', {'POST'}, 'voice:write'),
    (r'^/v1/voice/sessions/[^/]+$', {'DELETE'}, 'voice:delete'),
    (r'^/v1/voice/', {'GET'}, 'voice:read'),
    # ── Ralph Router (/v1/ralph) ─────────────────────────────────
    (r'^/v1/ralph/runs$', {'POST'}, 'ralph:write'),
    (r'^/v1/ralph/recover$', {'POST'}, 'ralph:write'),
    (r'^/v1/ralph/runs/[^/]+/cancel$', {'POST'}, 'ralph:write'),
    (r'^/v1/ralph/runs/[^/]+$', {'DELETE'}, 'ralph:delete'),
    (r'^/v1/ralph/chat$', {'POST'}, 'ralph:write'),
    (r'^/v1/ralph/', {'GET'}, 'ralph:read'),
    # ── Proactive Router (/v1/proactive) ──────────────────────────
    (r'^/v1/proactive/rules$', {'POST'}, 'proactive:write'),
    (r'^/v1/proactive/rules/[^/]+$', {'PUT'}, 'proactive:write'),
    (r'^/v1/proactive/rules/[^/]+$', {'DELETE'}, 'proactive:delete'),
    (r'^/v1/proactive/rules/[^/]+/trigger$', {'POST'}, 'proactive:write'),
    (r'^/v1/proactive/health-checks$', {'POST'}, 'proactive:write'),
    (r'^/v1/proactive/health-checks/[^/]+$', {'PUT'}, 'proactive:write'),
    (r'^/v1/proactive/health-checks/[^/]+$', {'DELETE'}, 'proactive:delete'),
    (r'^/v1/proactive/loops$', {'POST'}, 'proactive:write'),
    (r'^/v1/proactive/loops/[^/]+$', {'PUT'}, 'proactive:write'),
    (r'^/v1/proactive/loops/[^/]+$', {'DELETE'}, 'proactive:delete'),
    (r'^/v1/proactive/decisions', {'GET'}, 'decisions:read'),
    (r'^/v1/proactive/', {'GET'}, 'proactive:read'),
    # ── Email Routers (/v1/email) ────────────────────────────────
    # Inbound webhook — should verify signature, but at minimum needs auth
    (r'^/v1/email/inbound$', {'POST'}, 'email:write'),
    # All other email endpoints are admin/debug
    (r'^/v1/email/', None, 'email:admin'),
    # ── Analytics Router (/v1/analytics) ─────────────────────────
    # Client-side tracking endpoints — require basic auth
    (r'^/v1/analytics/track$', {'POST'}, 'analytics:write'),
    (r'^/v1/analytics/identify$', {'POST'}, 'analytics:write'),
    (r'^/v1/analytics/page$', {'POST'}, 'analytics:write'),
    # Admin analytics endpoints
    (r'^/v1/analytics/', None, 'analytics:admin'),
    # ── MCP Router (/mcp) ────────────────────────────────────────
    # Zero trust: MCP exposes task creation, messaging, and codebase deletion.
    # It was previously skipped ("internal protocol") and reachable
    # anonymously from the internet. Discovery stays public (MCP spec);
    # everything else needs an authenticated identity with mcp scope.
    (r'^/mcp/?$', {'GET'}, ''),
    (r'^/mcp/v1/tools$', {'GET'}, 'mcp:read'),
    (r'^/mcp/v1/tasks', {'GET'}, 'mcp:read'),
    (r'^/mcp', None, 'mcp:write'),
    # ── Token Billing Router (/v1/token-billing) ─────────────────
    (r'^/v1/token-billing/budgets', {'POST', 'PUT', 'DELETE'}, 'billing:write'),
    (r'^/v1/token-billing/pricing', {'POST', 'PUT', 'DELETE'}, 'billing:write'),
    (r'^/v1/token-billing/', None, 'billing:read'),
    # ── Worker SSE (/v1/worker) — has its own token auth ─────────
    (r'^/v1/worker/', None, ''),
    # ── A2A Protocol (/a2a) ──────────────────────────────────────
    # Zero trust: A2A message/send creates and queues real agent work. The
    # routes were skipped ("optional auth") and ran work for anonymous
    # callers. Discovery (agent card) stays public per the A2A spec.
    (r'^/a2a/card$', {'GET'}, ''),
    (r'^/a2a/rest/tasks/', {'GET'}, 'tasks:read'),
    (r'^/a2a/', None, 'tasks:execute'),
    # ── Server inline routes ─────────────────────────────────────
    (r'^/agents$', {'GET'}, 'agent:read'),
    (r'^/v1/livekit/token$', {'POST'}, ''),  # has its own auth
    (r'^/v1/a2a$', {'POST'}, 'tasks:execute'),  # A2A JSON-RPC
    (r'^/$', {'POST'}, 'tasks:execute'),  # A2A JSON-RPC root
]

# Pre-compile regexes for performance.
_COMPILED_RULES = [
    (re.compile(pattern), methods, perm) for pattern, methods, perm in _RULES
]


def _match_permission(path: str, method: str) -> str | None:
    """Find the required permission for a path + method.

    Returns:
        - permission string if auth is required
        - "" (empty string) if the route should be skipped
        - None if no rule matches (pass through)
    """
    for regex, methods, perm in _COMPILED_RULES:
        if regex.search(path) and (methods is None or method in methods):
            return perm
    return None


def _authentication_required(permission: str) -> JSONResponse:
    """401 with an RFC 9728 / MCP-spec ``WWW-Authenticate`` challenge."""
    return JSONResponse(
        status_code=401,
        content={'detail': 'Authentication required'},
        headers={'WWW-Authenticate': www_authenticate_header(scope=permission)},
    )


def _insufficient_scope(permission: str) -> JSONResponse:
    """403 with an RFC 6750 ``insufficient_scope`` challenge."""
    resource_metadata = f'{_SERVER_URL}/.well-known/oauth-protected-resource'
    return JSONResponse(
        status_code=403,
        content={
            'detail': (
                f"Access denied: insufficient permissions for '{permission}'"
            )
        },
        headers={
            'WWW-Authenticate': (
                f'Bearer error="insufficient_scope", '
                f'scope="{permission}", '
                f'resource_metadata="{resource_metadata}"'
            )
        },
    )


class PolicyAuthorizationMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that enforces OPA policies on matched routes."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Authenticate, then authorize the request against its route rule."""
        if not policy.OPA_ENABLED:
            return await call_next(request)

        path = request.url.path
        method = request.method
        permission = _match_permission(path, method)
        skip = permission is None or permission == ''

        # Worker infrastructure paths: zero trust, never open by default.
        # Accept a valid worker token or an allow-listed identity.
        # Only the public chat POST and an explicit dev opt-in bypass this.
        if _WORKER_PATH.search(path) and not _worker_path_exempt(path, method):
            verdict = await self._authorize_worker(request, path)
            if verdict is not None:
                return verdict
            if skip or request.state.worker_token:
                return await call_next(request)

        if not skip:
            verdict = await self._authorize_user(request, permission)
            if verdict is not None:
                return verdict
        return await call_next(request)

    async def _authorize_user(
        self, request: Request, permission: str
    ) -> JSONResponse | None:
        """Resolve the caller and check ``permission``; None means allowed."""
        user = await self._resolve_user(request)
        if user is None:
            return _authentication_required(permission)
        if not await policy.check_policy(user, permission):
            logger.warning(
                'policy_middleware_denied',
                extra={
                    'user_id': user.get('user_id') or user.get('id'),
                    'action': permission,
                    'path': request.url.path,
                    'method': request.method,
                },
            )
            return _insufficient_scope(permission)
        request.state.policy_user = user
        return None

    async def _authorize_worker(
        self, request: Request, path: str
    ) -> JSONResponse | None:
        """Gate a worker-path request; return a rejection or None to allow.

        Sets ``request.state.worker_token`` when a shared worker token
        authenticated the call (legacy path, closed in SPIRE-native mode).
        """
        request.state.worker_token = bool(
            WORKER_AUTH_TOKEN
            and not _spiffe_only_workers()
            and self._check_worker_token(request)
        )
        if request.state.worker_token:
            return None
        user = await self._resolve_user(request)
        if user is None:
            return _worker_auth_required()
        if not worker_identity_allowed(user):
            logger.warning(
                'SPIFFE identity %s not allowed on worker path %s',
                user.get('spiffe_id'),
                path,
            )
            return JSONResponse(
                status_code=403,
                content={'detail': 'Workload not authorized as worker'},
            )
        request.state.policy_user = user
        return None

    async def _resolve_user(self, request: Request) -> dict | None:
        """Resolve authenticated user from the request."""
        return await policy._resolve_user(request)  # noqa: SLF001 - shared

    @staticmethod
    def _check_worker_token(request: Request) -> bool:
        """Validate a worker Bearer token against WORKER_AUTH_TOKEN."""
        auth = request.headers.get('authorization', '')
        if not auth.startswith('Bearer '):
            return False
        token = auth[7:]
        return hmac.compare_digest(token, WORKER_AUTH_TOKEN)