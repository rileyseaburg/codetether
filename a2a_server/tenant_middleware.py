"""
Tenant Context Middleware for A2A Server.

Extracts tenant context from JWT tokens and makes it available
in request.state for downstream handlers.
"""

import logging
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

try:
    from jose import jwt
except ImportError:
    jwt = None  # type: ignore

from . import database

logger = logging.getLogger(__name__)


class TenantContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware that extracts tenant context from JWT tokens.

    Extracts the realm from the 'iss' claim in the JWT and looks up
    the corresponding tenant_id from the database. Stores tenant
    information in request.state for use by downstream handlers.

    Attributes stored in request.state:
        - tenant_id: The database tenant ID (or None if not found)
        - realm_name: The Keycloak realm name (or None if not found)
        - tenant_plan: The tenant's subscription plan (or None if not found)
    """

    async def dispatch(self, request: Request, call_next):
        """Process the request and extract tenant context."""
        # Initialize tenant context as None
        request.state.tenant_id = None
        request.state.realm_name = None
        request.state.tenant_plan = None

        # Try to extract tenant from Authorization header
        try:
            tenant_info = await self._extract_tenant_from_request(request)
            if tenant_info:
                request.state.tenant_id = tenant_info.get('id')
                request.state.realm_name = tenant_info.get('realm_name')
                request.state.tenant_plan = tenant_info.get('plan')
                logger.debug(
                    f'Tenant context set: {request.state.realm_name} '
                    f'(id={request.state.tenant_id}, plan={request.state.tenant_plan})'
                )
        except Exception as e:
            # Log but don't fail - allow unauthenticated requests
            logger.debug(f'Could not extract tenant context: {e}')

        # Continue processing the request
        response = await call_next(request)
        return response

    async def _extract_tenant_from_request(
        self, request: Request
    ) -> Optional[dict]:
        """
        Extract tenant information from the request's JWT token.

        Args:
            request: The incoming request

        Returns:
            Tenant dict if found, None otherwise
        """
        # Get Authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return None

        # Extract Bearer token
        if not auth_header.startswith('Bearer '):
            return None

        token = auth_header[7:]  # Remove 'Bearer ' prefix
        if not token:
            return None

        # Extract realm from token
        realm_name = self._extract_realm_from_token(token)
        if not realm_name:
            return None

        # Look up tenant from database
        tenant = await database.get_tenant_by_realm(realm_name)
        return tenant

    def _extract_realm_from_token(self, token: str) -> Optional[str]:
        """
        Extract the realm name from a JWT token's 'iss' claim.

        Uses unverified claims extraction for performance - full
        validation should be done by the auth layer.

        Args:
            token: The JWT token string

        Returns:
            The realm name or None if extraction fails
        """
        if jwt is None:
            logger.warning(
                'python-jose not installed, cannot extract realm from JWT'
            )
            return None

        try:
            # Get unverified claims for fast extraction
            # Full validation is done by the auth layer
            claims = jwt.get_unverified_claims(token)

            # Extract issuer claim
            issuer = claims.get('iss')
            if not issuer:
                return None

            # Parse realm from issuer URL
            # Format: https://keycloak.example.com/realms/realm-name
            # or: https://keycloak.example.com/auth/realms/realm-name
            realm_name = self._parse_realm_from_issuer(issuer)
            return realm_name

        except Exception as e:
            logger.debug(f'Failed to extract realm from token: {e}')
            return None

    def _parse_realm_from_issuer(self, issuer: str) -> Optional[str]:
        """
        Parse the realm name from a Keycloak issuer URL.

        Args:
            issuer: The issuer URL from the JWT

        Returns:
            The realm name or None if parsing fails
        """
        if not issuer:
            return None

        # Handle both /realms/ and /auth/realms/ formats
        if '/realms/' in issuer:
            # Extract everything after /realms/
            parts = issuer.split('/realms/')
            if len(parts) >= 2:
                # Get the realm part, removing any trailing path
                realm_part = parts[1]
                # Remove any trailing path segments
                realm_name = realm_part.split('/')[0]
                return realm_name if realm_name else None

        return None


def get_tenant_id(request: Request) -> Optional[str]:
    """
    Helper function to get tenant_id from request state.

    Args:
        request: The request object

    Returns:
        The tenant_id or None if not set
    """
    return getattr(request.state, 'tenant_id', None)


def get_realm_name(request: Request) -> Optional[str]:
    """
    Helper function to get realm_name from request state.

    Args:
        request: The request object

    Returns:
        The realm_name or None if not set
    """
    return getattr(request.state, 'realm_name', None)


def get_tenant_plan(request: Request) -> Optional[str]:
    """
    Helper function to get tenant_plan from request state.

    Args:
        request: The request object

    Returns:
        The tenant_plan or None if not set
    """
    return getattr(request.state, 'tenant_plan', None)


def require_tenant(request: Request) -> str:
    """
    Helper function that requires a tenant_id to be present.

    Args:
        request: The request object

    Returns:
        The tenant_id

    Raises:
        ValueError: If no tenant_id is present
    """
    tenant_id = get_tenant_id(request)
    if not tenant_id:
        raise ValueError('Tenant context required but not found')
    return tenant_id
