"""
Budget Enforcement Middleware for A2A Server.

Pre-request middleware that checks tenant token budgets before allowing
AI operations through. Blocks or warns when spending limits are exceeded.

Integrates with:
- Token billing service (balance checks)
- FinOps service (budget policy evaluation)
- Tenant context middleware (tenant_id extraction)
"""

import logging
import re
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# Routes that trigger AI operations and should be budget-checked.
# These are the endpoints that actually consume tokens.
_BUDGET_CHECK_ROUTES = [
    re.compile(r'^/v1/agent/tasks/?$'),           # Create task
    re.compile(r'^/v1/automation/tasks/?$'),       # Automation task creation
    re.compile(r'^/mcp$'),                         # MCP tool invocations
    re.compile(r'^/v1/agent/send-message/?$'),     # Send message to agent
    re.compile(r'^/v1/agent/codebases/.+/sessions/.+/messages$'),  # Session message
]

_BUDGET_CHECK_METHODS = {'POST', 'PUT'}


def _requires_budget_check(path: str, method: str) -> bool:
    """Determine if a request path needs a budget check."""
    if method not in _BUDGET_CHECK_METHODS:
        return False
    return any(pattern.search(path) for pattern in _BUDGET_CHECK_ROUTES)


class BudgetEnforcementMiddleware(BaseHTTPMiddleware):
    """
    Starlette middleware that enforces token budgets before AI operations.

    Checks:
    1. Prepaid balance > 0
    2. Monthly spending limit not exceeded
    3. Budget policies not in 'block' state

    Non-AI routes pass through without checks.
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        method = request.method

        # Only check routes that consume AI tokens
        if not _requires_budget_check(path, method):
            return await call_next(request)

        # Get tenant_id from request state (set by TenantContextMiddleware)
        tenant_id = getattr(request.state, 'tenant_id', None)
        if not tenant_id:
            # No tenant context = can't enforce budget, pass through
            return await call_next(request)

        try:
            from .finops import get_finops_service
            finops = get_finops_service()

            allowed, reason = await finops.enforce_budget(tenant_id)

            if not allowed:
                logger.warning(
                    f'Budget enforcement blocked request: tenant={tenant_id} '
                    f'path={path} reason={reason}'
                )
                return JSONResponse(
                    status_code=402,  # Payment Required
                    content={
                        'detail': reason or 'Budget limit reached',
                        'error_code': 'BUDGET_EXCEEDED',
                        'upgrade_url': '/dashboard/billing',
                    },
                )

        except Exception as e:
            # Fail open - don't block requests due to middleware errors
            logger.error(f'Budget enforcement middleware error: {e}')

        return await call_next(request)
