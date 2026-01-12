"""
Tenant Management REST API for A2A Server.

Provides endpoints for tenant provisioning, management, and administration:
- Public signup for new tenants
- Tenant details retrieval
- Admin management of tenants
- Super-admin listing of all tenants
"""

import logging
import re
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from .database import (
    create_tenant,
    get_tenant_by_id,
    get_tenant_by_realm,
    list_tenants,
    update_tenant,
)
from .keycloak_auth import require_admin, require_auth, UserSession
from .tenant_service import KeycloakTenantService, TenantAlreadyExistsError

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/v1/tenants', tags=['tenants'])


# ========================================
# Request/Response Models
# ========================================


class TenantSignupRequest(BaseModel):
    """Request model for tenant signup."""

    org_name: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description='Organization name (3-50 chars, alphanumeric and spaces)',
    )
    admin_email: str = Field(..., description='Admin user email address')
    admin_password: str = Field(
        ..., min_length=8, description='Admin user password (min 8 chars)'
    )
    plan: Optional[str] = Field(
        default='free', description='Subscription plan (free, pro, enterprise)'
    )

    @field_validator('org_name')
    @classmethod
    def validate_org_name(cls, v: str) -> str:
        """Validate org_name contains only alphanumeric characters and spaces."""
        if not re.match(r'^[a-zA-Z0-9 ]+$', v):
            raise ValueError(
                'Organization name must contain only alphanumeric characters and spaces'
            )
        return v


class TenantSignupResponse(BaseModel):
    """Response model for successful tenant signup."""

    tenant_id: str = Field(..., description='Unique tenant identifier')
    realm_name: str = Field(..., description='Keycloak realm name')
    login_url: str = Field(..., description='URL for user authentication')
    spa_client_id: str = Field(
        ..., description='Client ID for SPA applications'
    )


class TenantResponse(BaseModel):
    """Response model for tenant details."""

    id: str
    realm_name: str
    display_name: Optional[str]
    plan: str
    stripe_customer_id: Optional[str]
    stripe_subscription_id: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]


class TenantUpdateRequest(BaseModel):
    """Request model for tenant updates."""

    display_name: Optional[str] = Field(
        default=None, description='Human-readable tenant name'
    )
    plan: Optional[str] = Field(
        default=None, description='Subscription plan (free, pro, enterprise)'
    )


class TenantListResponse(BaseModel):
    """Response model for tenant listing."""

    tenants: List[TenantResponse]
    total: int
    limit: int
    offset: int


# ========================================
# Helper Functions
# ========================================


def generate_slug(org_name: str) -> str:
    """
    Generate a URL-safe slug from organization name.

    - Converts to lowercase
    - Replaces spaces with hyphens
    - Removes special characters
    """
    slug = org_name.lower()
    slug = slug.replace(' ', '-')
    slug = re.sub(r'[^a-z0-9-]', '', slug)
    # Remove consecutive hyphens
    slug = re.sub(r'-+', '-', slug)
    # Remove leading/trailing hyphens
    slug = slug.strip('-')
    return slug


# ========================================
# Endpoints
# ========================================


@router.post('/signup', response_model=TenantSignupResponse, status_code=201)
async def signup_tenant(request: TenantSignupRequest):
    """
    Create a new tenant (public endpoint, no auth required).

    This endpoint provisions:
    - A new Keycloak realm for the organization
    - Standard OAuth clients (SPA, API, Mobile)
    - An admin user with the provided credentials
    - A database record for the tenant

    Returns login URL and client credentials for the new tenant.
    """
    # Generate slug from org name
    slug = generate_slug(request.org_name)

    if not slug:
        raise HTTPException(
            status_code=400,
            detail='Invalid organization name - could not generate slug',
        )

    logger.info(f'Tenant signup request for: {request.org_name} (slug: {slug})')

    try:
        # Create tenant in Keycloak
        keycloak_service = KeycloakTenantService()
        tenant_info = await keycloak_service.create_tenant(
            org_slug=slug,
            admin_email=request.admin_email,
            admin_password=request.admin_password,
        )

        # Store tenant in database
        db_tenant = await create_tenant(
            realm_name=tenant_info.realm_name,
            display_name=request.org_name,
            plan=request.plan or 'free',
        )

        # Build login URL
        from .keycloak_auth import KEYCLOAK_URL

        login_url = f'{KEYCLOAK_URL}/realms/{tenant_info.realm_name}/protocol/openid-connect/auth'

        logger.info(
            f'Tenant created successfully: {tenant_info.realm_name} (id: {db_tenant["id"]})'
        )

        return TenantSignupResponse(
            tenant_id=db_tenant['id'],
            realm_name=tenant_info.realm_name,
            login_url=login_url,
            spa_client_id=tenant_info.spa_client_id,
        )

    except TenantAlreadyExistsError as e:
        logger.warning(f'Tenant already exists: {slug}')
        raise HTTPException(
            status_code=409,
            detail=f'A tenant with this organization name already exists: {str(e)}',
        )
    except Exception as e:
        logger.error(f'Failed to create tenant: {e}')
        raise HTTPException(
            status_code=500,
            detail=f'Failed to create tenant: {str(e)}',
        )


@router.get('/me', response_model=TenantResponse)
async def get_my_tenant(user: UserSession = Depends(require_auth)):
    """
    Get the current user's tenant details.

    Requires authentication. Returns the tenant associated with the
    authenticated user's tenant_id.
    """
    # Get tenant_id from user session
    tenant_id = getattr(user, 'tenant_id', None)

    if not tenant_id:
        # Try to find tenant by realm from the token issuer
        # The realm is typically in the format: org-slug.codetether.run
        raise HTTPException(
            status_code=404,
            detail='No tenant associated with this user',
        )

    tenant = await get_tenant_by_id(tenant_id)

    if not tenant:
        raise HTTPException(
            status_code=404,
            detail='Tenant not found',
        )

    return TenantResponse(**tenant)


@router.get('/{tenant_id}', response_model=TenantResponse)
async def get_tenant(
    tenant_id: str,
    user: UserSession = Depends(require_admin),
):
    """
    Get tenant details by ID.

    Requires admin role.
    """
    tenant = await get_tenant_by_id(tenant_id)

    if not tenant:
        raise HTTPException(
            status_code=404,
            detail=f'Tenant {tenant_id} not found',
        )

    return TenantResponse(**tenant)


@router.patch('/{tenant_id}', response_model=TenantResponse)
async def update_tenant_details(
    tenant_id: str,
    request: TenantUpdateRequest,
    user: UserSession = Depends(require_admin),
):
    """
    Update tenant details.

    Requires admin role. Only display_name and plan can be updated.
    """
    # Check if tenant exists
    existing = await get_tenant_by_id(tenant_id)
    if not existing:
        raise HTTPException(
            status_code=404,
            detail=f'Tenant {tenant_id} not found',
        )

    # Build update kwargs (only include non-None values)
    update_kwargs = {}
    if request.display_name is not None:
        update_kwargs['display_name'] = request.display_name
    if request.plan is not None:
        update_kwargs['plan'] = request.plan

    if not update_kwargs:
        # Nothing to update, return current tenant
        return TenantResponse(**existing)

    try:
        updated_tenant = await update_tenant(tenant_id, **update_kwargs)
        logger.info(f'Tenant {tenant_id} updated: {update_kwargs}')
        return TenantResponse(**updated_tenant)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f'Failed to update tenant {tenant_id}: {e}')
        raise HTTPException(
            status_code=500,
            detail=f'Failed to update tenant: {str(e)}',
        )


@router.get('', response_model=TenantListResponse)
async def list_all_tenants(
    limit: int = Query(
        default=100, ge=1, le=1000, description='Maximum results'
    ),
    offset: int = Query(default=0, ge=0, description='Results offset'),
    user: UserSession = Depends(require_auth),
):
    """
    List all tenants.

    Requires super-admin role (user must have 'super-admin' in their roles).
    """
    # Check for super-admin role
    if 'super-admin' not in user.roles:
        raise HTTPException(
            status_code=403,
            detail='Super-admin access required to list all tenants',
        )

    tenants = await list_tenants(limit=limit, offset=offset)

    return TenantListResponse(
        tenants=[TenantResponse(**t) for t in tenants],
        total=len(
            tenants
        ),  # Note: This is approximate; full count would require additional query
        limit=limit,
        offset=offset,
    )
