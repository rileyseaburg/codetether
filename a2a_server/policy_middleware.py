"""
Centralized Authorization Middleware for A2A Server.

Maps HTTP path patterns + methods to OPA permission strings and enforces
authorization via the policy engine. This secures ~120 previously-unprotected
endpoints without modifying individual route signatures.

Endpoints that are intentionally public or already protected by existing
auth dependencies are skipped.
"""

import os
import re
import hmac
import logging
from typing import Optional, List, Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# ── Worker Authentication ────────────────────────────────────────
# When WORKER_AUTH_TOKEN is set, worker infrastructure endpoints require
# this token as Bearer auth. When unset, worker endpoints remain open
# for backward compatibility with internal deployments.
WORKER_AUTH_TOKEN: Optional[str] = os.environ.get('WORKER_AUTH_TOKEN')
_WORKER_PATH = re.compile(
    r'^/v1/agent/(workers/|tasks$)'
)


# ── Path → Permission Mapping ────────────────────────────────────
#
# Each rule is (path_regex, http_methods, permission_action).
# Rules are evaluated top-to-bottom; first match wins.
# Use None for http_methods to match any method.
#
# Endpoints NOT listed here pass through without middleware-level
# authorization (they may still have their own auth dependencies).

_RULES: List[Tuple[str, Optional[set], str]] = [
    # ── Public / Skip (no auth required) ─────────────────────────
    # These return "" to signal "skip authorization".
    (r"^/health$", None, ""),
    (r"^/\.well-known/", None, ""),
    (r"^/static/", None, ""),
    (r"^/docs", None, ""),
    (r"^/openapi\.json$", None, ""),
    (r"^/redoc", None, ""),

    # Auth endpoints — intentionally public
    (r"^/v1/auth/login$", None, ""),
    (r"^/v1/auth/refresh$", None, ""),
    (r"^/v1/auth/logout$", None, ""),
    (r"^/v1/auth/status$", None, ""),
    (r"^/api/auth/", None, ""),  # NextAuth compat — all public

    # User auth — public endpoints
    (r"^/v1/users/register$", {"POST"}, ""),
    (r"^/v1/users/login$", {"POST"}, ""),
    (r"^/v1/users/password-reset/", None, ""),

    # Tenant signup — public
    (r"^/v1/tenants/signup$", {"POST"}, ""),

    # A2A protocol discovery
    (r"^/a2a/\.well-known/", None, ""),

    # Agent discovery — read-only model/provider listing
    (r"^/v1/agent/models$", {"GET"}, ""),
    (r"^/v1/agent/providers$", {"GET"}, ""),

    # Billing webhooks — Stripe signature verified
    (r"^/v1/webhooks/stripe$", {"POST"}, ""),

    # ── Already-protected routes (skip to avoid double auth) ─────
    # Billing, admin, tenant (non-signup), user auth (non-public),
    # cronjobs, queue — all have existing Depends(require_*).
    (r"^/v1/billing/", None, ""),
    (r"^/v1/admin/", None, ""),
    (r"^/v1/tenants/", None, ""),  # signup already skipped above
    (r"^/v1/users/", None, ""),    # public endpoints already skipped above
    (r"^/v1/cronjobs", None, ""),
    (r"^/v1/queue/", None, ""),

    # Legacy redirect — just passes through
    (r"^/v1/opencode/", None, ""),

    # ── Monitor Router (/v1/monitor) ─────────────────────────────
    (r"^/v1/monitor/intervene$", {"POST"}, "monitor:write"),
    (r"^/v1/monitor/export/", {"GET"}, "monitor:read"),
    (r"^/v1/monitor", None, "monitor:read"),

    # ── Agent Router (/v1/agent) ─────────────────────────────────
    # Database admin endpoints
    (r"^/v1/agent/database/codebases/deduplicate$", {"POST"}, "admin:access"),
    (r"^/v1/agent/database/", None, "admin:access"),
    (r"^/v1/agent/reaper/", None, "admin:access"),
    (r"^/v1/agent/vault/", None, "admin:access"),
    (r"^/v1/agent/tasks/stuck", None, "admin:access"),

    # API keys (already have soft auth, reinforce with policy)
    (r"^/v1/agent/api-keys$", {"GET"}, "api_keys:read"),
    (r"^/v1/agent/api-keys$", {"POST"}, "api_keys:write"),
    (r"^/v1/agent/api-keys/sync$", {"GET"}, "api_keys:read"),
    (r"^/v1/agent/api-keys/test$", {"POST"}, "api_keys:write"),
    (r"^/v1/agent/api-keys/", {"DELETE"}, "api_keys:delete"),

    # Worker management — registration, heartbeat, task-polling, and claiming
    # are internal infrastructure (workers run on trusted nodes), so skip auth.
    (r"^/v1/agent/workers/register$", {"POST"}, ""),
    (r"^/v1/agent/workers/[^/]+/unregister$", {"POST"}, ""),
    (r"^/v1/agent/workers/[^/]+/heartbeat$", {"POST"}, ""),
    (r"^/v1/agent/tasks$", {"GET"}, ""),  # worker task polling (status=pending)
    (r"^/v1/agent/workers/[^/]+/profile$", {"POST"}, "workers:write"),
    (r"^/v1/agent/workers$", {"GET"}, ""),
    (r"^/v1/agent/workers/", {"GET"}, ""),

    # Worker profiles
    (r"^/v1/agent/worker-profiles$", {"POST"}, "workers:write"),
    (r"^/v1/agent/worker-profiles$", {"GET"}, "workers:read"),
    (r"^/v1/agent/worker-profiles/", {"GET"}, "workers:read"),
    (r"^/v1/agent/worker-profiles/", {"PATCH"}, "workers:write"),
    (r"^/v1/agent/worker-profiles/", {"DELETE"}, "workers:delete"),

    # Codebase mutations
    (r"^/v1/agent/codebases$", {"POST"}, "codebases:write"),
    (r"^/v1/agent/codebases/[^/]+/trigger$", {"POST"}, "codebases:write"),
    (r"^/v1/agent/codebases/[^/]+/message$", {"POST"}, "codebases:write"),
    (r"^/v1/agent/codebases/[^/]+/interrupt$", {"POST"}, "codebases:write"),
    (r"^/v1/agent/codebases/[^/]+/stop$", {"POST"}, "codebases:write"),
    (r"^/v1/agent/codebases/[^/]+/upload$", {"POST"}, "codebases:write"),
    (r"^/v1/agent/codebases/[^/]+/sync$", {"POST"}, "codebases:write"),
    (r"^/v1/agent/codebases/[^/]+/watch/start$", {"POST"}, "codebases:write"),
    (r"^/v1/agent/codebases/[^/]+/watch/stop$", {"POST"}, "codebases:write"),
    (r"^/v1/agent/codebases/[^/]+$", {"DELETE"}, "codebases:delete"),

    # Session mutations (before codebase GET catch-all)
    (r"^/v1/agent/codebases/[^/]+/sessions/[^/]+/ingest$", {"POST"}, "sessions:write"),
    (r"^/v1/agent/codebases/[^/]+/sessions/sync$", {"POST"}, "sessions:write"),
    (r"^/v1/agent/codebases/[^/]+/sessions/[^/]+/resume$", {"POST"}, "sessions:write"),

    # Session reads
    (r"^/v1/agent/codebases/[^/]+/sessions", {"GET"}, "sessions:read"),
    (r"^/v1/agent/runtime/sessions/[^/]+/messages$", {"GET"}, "sessions:read"),
    (r"^/v1/agent/runtime/sessions/[^/]+/parts$", {"GET"}, "sessions:read"),
    (r"^/v1/agent/runtime/sessions/", {"GET"}, "sessions:read"),
    (r"^/v1/agent/sessions/[^/]+/worker-status$", {"GET"}, "sessions:read"),

    # Task mutations
    (r"^/v1/agent/tasks$", {"POST"}, "tasks:write"),
    (r"^/v1/agent/codebases/[^/]+/tasks$", {"POST"}, "tasks:write"),
    (r"^/v1/agent/tasks/[^/]+/cancel$", {"POST"}, "tasks:write"),
    (r"^/v1/agent/tasks/[^/]+/status$", {"PUT"}, "tasks:write"),
    (r"^/v1/agent/tasks/[^/]+/output$", {"POST"}, "tasks:write"),
    (r"^/v1/agent/tasks/[^/]+/requeue$", {"POST"}, "tasks:write"),

    # Codebase/task GET catch-all (AFTER specific session/task sub-paths)
    (r"^/v1/agent/codebases/[^/]+/tasks$", {"GET"}, "tasks:read"),
    (r"^/v1/agent/codebases", {"GET"}, "codebases:read"),

    # Task reads
    (r"^/v1/agent/tasks", {"GET"}, "tasks:read"),

    # Agent info reads (status, runtime, models, providers)
    (r"^/v1/agent/status$", {"GET"}, "agent:read"),
    (r"^/v1/agent/runtime/", {"GET"}, "agent:read"),
    (r"^/v1/agent/models$", {"GET"}, "agent:read"),
    (r"^/v1/agent/providers$", {"GET"}, "agent:read"),

    # ── Auth Router — protected user endpoints ───────────────────
    (r"^/v1/auth/session$", {"GET"}, "sessions:read"),
    (r"^/v1/auth/sync$", {"GET"}, "sessions:read"),
    (r"^/v1/auth/user/[^/]+/codebases$", {"GET"}, "codebases:read"),
    (r"^/v1/auth/user/[^/]+/codebases$", {"POST"}, "codebases:write"),
    (r"^/v1/auth/user/[^/]+/codebases/", {"DELETE"}, "codebases:delete"),
    (r"^/v1/auth/user/[^/]+/agent-sessions$", {"GET"}, "sessions:read"),
    (r"^/v1/auth/user/[^/]+/agent-sessions$", {"POST"}, "sessions:write"),
    (r"^/v1/auth/agent-sessions/", {"GET"}, "sessions:read"),
    (r"^/v1/auth/agent-sessions/", {"DELETE"}, "sessions:delete"),

    # ── Voice Router (/v1/voice) ─────────────────────────────────
    (r"^/v1/voice/sessions$", {"POST"}, "voice:write"),
    (r"^/v1/voice/sessions/[^/]+$", {"DELETE"}, "voice:delete"),
    (r"^/v1/voice/", {"GET"}, "voice:read"),

    # ── Ralph Router (/v1/ralph) ─────────────────────────────────
    (r"^/v1/ralph/runs$", {"POST"}, "ralph:write"),
    (r"^/v1/ralph/recover$", {"POST"}, "ralph:write"),
    (r"^/v1/ralph/runs/[^/]+/cancel$", {"POST"}, "ralph:write"),
    (r"^/v1/ralph/runs/[^/]+$", {"DELETE"}, "ralph:delete"),
    (r"^/v1/ralph/chat$", {"POST"}, "ralph:write"),
    (r"^/v1/ralph/", {"GET"}, "ralph:read"),

    # ── Proactive Router (/v1/proactive) ──────────────────────────
    (r"^/v1/proactive/rules$", {"POST"}, "proactive:write"),
    (r"^/v1/proactive/rules/[^/]+$", {"PUT"}, "proactive:write"),
    (r"^/v1/proactive/rules/[^/]+$", {"DELETE"}, "proactive:delete"),
    (r"^/v1/proactive/rules/[^/]+/trigger$", {"POST"}, "proactive:write"),
    (r"^/v1/proactive/health-checks$", {"POST"}, "proactive:write"),
    (r"^/v1/proactive/health-checks/[^/]+$", {"PUT"}, "proactive:write"),
    (r"^/v1/proactive/health-checks/[^/]+$", {"DELETE"}, "proactive:delete"),
    (r"^/v1/proactive/loops$", {"POST"}, "proactive:write"),
    (r"^/v1/proactive/loops/[^/]+$", {"PUT"}, "proactive:write"),
    (r"^/v1/proactive/loops/[^/]+$", {"DELETE"}, "proactive:delete"),
    (r"^/v1/proactive/decisions", {"GET"}, "decisions:read"),
    (r"^/v1/proactive/", {"GET"}, "proactive:read"),

    # ── Email Routers (/v1/email) ────────────────────────────────
    # Inbound webhook — should verify signature, but at minimum needs auth
    (r"^/v1/email/inbound$", {"POST"}, "email:write"),
    # All other email endpoints are admin/debug
    (r"^/v1/email/", None, "email:admin"),

    # ── Analytics Router (/v1/analytics) ─────────────────────────
    # Client-side tracking endpoints — require basic auth
    (r"^/v1/analytics/track$", {"POST"}, "analytics:write"),
    (r"^/v1/analytics/identify$", {"POST"}, "analytics:write"),
    (r"^/v1/analytics/page$", {"POST"}, "analytics:write"),
    # Admin analytics endpoints
    (r"^/v1/analytics/", None, "analytics:admin"),

    # ── MCP Router (/mcp) ────────────────────────────────────────
    (r"^/mcp/v1/rpc$", {"POST"}, "mcp:write"),
    (r"^/mcp/v1/message$", {"POST"}, "mcp:write"),
    (r"^/mcp/v1/tasks$", {"POST"}, "mcp:write"),
    (r"^/mcp$", {"POST"}, "mcp:write"),
    (r"^/mcp", {"GET"}, "mcp:read"),

    # ── Token Billing Router (/v1/token-billing) ─────────────────
    (r"^/v1/token-billing/budgets", {"POST", "PUT", "DELETE"}, "billing:write"),
    (r"^/v1/token-billing/pricing", {"POST", "PUT", "DELETE"}, "billing:write"),
    (r"^/v1/token-billing/", None, "billing:read"),

    # ── Worker SSE (/v1/worker) — has its own token auth ─────────
    (r"^/v1/worker/", None, ""),

    # ── A2A Protocol (/a2a) ──────────────────────────────────────
    (r"^/a2a/", None, ""),  # A2A has its own optional auth

    # ── Server inline routes ─────────────────────────────────────
    (r"^/agents$", {"GET"}, "agent:read"),
    (r"^/v1/livekit/token$", {"POST"}, ""),  # has its own auth
    (r"^/v1/a2a$", {"POST"}, ""),  # A2A protocol endpoint
    (r"^/$", {"POST"}, ""),  # JSON-RPC root — has its own auth
]

# Pre-compile regexes for performance.
_COMPILED_RULES = [(re.compile(pattern), methods, perm) for pattern, methods, perm in _RULES]


def _match_permission(path: str, method: str) -> Optional[str]:
    """Find the required permission for a path + method.

    Returns:
        - permission string if auth is required
        - "" (empty string) if the route should be skipped
        - None if no rule matches (pass through)
    """
    for regex, methods, perm in _COMPILED_RULES:
        if regex.search(path):
            if methods is None or method in methods:
                return perm
    return None


class PolicyAuthorizationMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that enforces OPA policies on matched routes."""

    async def dispatch(self, request: Request, call_next):
        from .policy import OPA_ENABLED

        # If policy engine is disabled globally, pass through.
        if not OPA_ENABLED:
            return await call_next(request)

        path = request.url.path
        method = request.method

        # Find applicable permission.
        permission = _match_permission(path, method)

        # No rule matched or explicitly skipped → pass through.
        if permission is None or permission == "":
            # Even on skip-auth routes, enforce worker token if configured.
            if WORKER_AUTH_TOKEN and _WORKER_PATH.search(path):
                if not self._check_worker_token(request):
                    return JSONResponse(
                        status_code=401,
                        content={"detail": "Worker authentication required (set --token on worker)"},
                    )
            return await call_next(request)

        # Resolve user from Authorization header.
        user = await self._resolve_user(request)
        if user is None:
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required"},
            )

        # Enforce policy.
        from .policy import check_policy

        allowed = await check_policy(user, permission)
        if not allowed:
            logger.warning(
                "policy_middleware_denied",
                extra={"user_id": user.get("user_id") or user.get("id"),
                       "action": permission, "path": path, "method": method}
            )
            return JSONResponse(
                status_code=403,
                content={
                    "detail": f"Access denied: insufficient permissions for '{permission}'"
                },
            )

        # Store resolved user on request state for downstream handlers.
        request.state.policy_user = user
        return await call_next(request)

    async def _resolve_user(self, request: Request) -> Optional[dict]:
        """Resolve authenticated user from the request."""
        from .policy import _resolve_user as _shared_resolve_user
        return await _shared_resolve_user(request)

    @staticmethod
    def _check_worker_token(request: Request) -> bool:
        """Validate Bearer token on worker endpoints against WORKER_AUTH_TOKEN."""
        auth = request.headers.get("authorization", "")
        if not auth.startswith("Bearer "):
            return False
        token = auth[7:]
        return hmac.compare_digest(token, WORKER_AUTH_TOKEN)
