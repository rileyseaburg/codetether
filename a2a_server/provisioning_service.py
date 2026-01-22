"""
Instance Provisioning Service for User Signup.

This module handles automatic instance/tenant provisioning when a new user signs up.
It follows the saga pattern for distributed transactions with proper rollback capabilities.

Provisioning includes:
1. Keycloak realm for authentication isolation
2. Database tenant record
3. Kubernetes deployment (dedicated pods for the user)

Best practices implemented:
- Single Responsibility: Dedicated service for provisioning logic
- Saga Pattern: Compensating transactions for rollback
- Idempotency: Safe to retry on failure
- Observability: Comprehensive logging
"""

import logging
import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from enum import Enum

from .database import get_pool, create_tenant
from .tenant_service import (
    KeycloakTenantService,
    TenantInfo,
    KeycloakTenantServiceError,
    TenantAlreadyExistsError,
)

logger = logging.getLogger(__name__)

# Feature flag for K8s provisioning
K8S_PROVISIONING_ENABLED = (
    os.environ.get('K8S_PROVISIONING_ENABLED', 'false').lower() == 'true'
)


class ProvisioningStatus(str, Enum):
    """Status of instance provisioning."""

    PENDING = 'pending'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
    FAILED = 'failed'
    ROLLED_BACK = 'rolled_back'


@dataclass
class ProvisioningResult:
    """Result of instance provisioning operation."""

    success: bool
    tenant_id: Optional[str] = None
    realm_name: Optional[str] = None
    # Kubernetes instance details
    k8s_namespace: Optional[str] = None
    k8s_external_url: Optional[str] = None
    k8s_internal_url: Optional[str] = None
    # Error handling
    error_message: Optional[str] = None
    status: ProvisioningStatus = ProvisioningStatus.PENDING

    def to_dict(self) -> dict:
        return {
            'success': self.success,
            'tenant_id': self.tenant_id,
            'realm_name': self.realm_name,
            'k8s_namespace': self.k8s_namespace,
            'k8s_external_url': self.k8s_external_url,
            'k8s_internal_url': self.k8s_internal_url,
            'error_message': self.error_message,
            'status': self.status.value,
        }


def generate_org_slug(email: str, first_name: Optional[str] = None) -> str:
    """
    Generate a unique organization slug from user info.

    Strategy:
    1. Use email local part as base
    2. Sanitize to alphanumeric + hyphens
    3. Add short UUID suffix for uniqueness

    Args:
        email: User's email address
        first_name: Optional first name for personalization

    Returns:
        A valid, unique organization slug
    """
    # Extract local part of email (before @)
    local_part = email.split('@')[0].lower()

    # Remove special characters, keep alphanumeric and hyphens
    slug_base = re.sub(
        r'[^a-z0-9-]', '', local_part.replace('.', '-').replace('_', '-')
    )

    # Collapse multiple hyphens
    slug_base = re.sub(r'-+', '-', slug_base).strip('-')

    # If too short, use first name or 'user'
    if len(slug_base) < 3:
        if first_name:
            slug_base = re.sub(r'[^a-z0-9-]', '', first_name.lower())
        if len(slug_base) < 3:
            slug_base = 'user'

    # Truncate if too long (max 20 chars for base)
    slug_base = slug_base[:20]

    # Add short unique suffix
    unique_suffix = uuid.uuid4().hex[:6]

    return f'{slug_base}-{unique_suffix}'


class InstanceProvisioningService:
    """
    Service for provisioning instances (tenants) for new users.

    Implements the saga pattern for distributed transactions:
    1. Create Keycloak realm (auth isolation)
    2. Create database tenant record
    3. Link user to tenant
    4. Create Kubernetes deployment (dedicated compute)

    If any step fails, previous steps are rolled back.
    """

    def __init__(self):
        self.keycloak_service = KeycloakTenantService()
        self.k8s_service = None

        # Lazy-load K8s service only if enabled
        if K8S_PROVISIONING_ENABLED:
            try:
                from .k8s_provisioning import k8s_provisioning_service

                self.k8s_service = k8s_provisioning_service
                logger.info('Kubernetes provisioning enabled')
            except ImportError as e:
                logger.warning(
                    f'K8s provisioning enabled but service unavailable: {e}'
                )

    async def provision_instance_for_user(
        self,
        user_id: str,
        email: str,
        password: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
    ) -> ProvisioningResult:
        """
        Provision a new instance (tenant) for a user.

        This is the main entry point for instance provisioning.
        Called after user registration to set up their isolated environment.

        Args:
            user_id: The newly created user's ID
            email: User's email address
            password: User's password (for Keycloak admin user)
            first_name: User's first name
            last_name: User's last name

        Returns:
            ProvisioningResult with success status and tenant details
        """
        logger.info(
            f'Starting instance provisioning for user {user_id} ({email})'
        )

        # Track provisioning state for rollback
        keycloak_realm_created = False
        tenant_created = False
        tenant_info: Optional[TenantInfo] = None
        db_tenant: Optional[dict] = None

        try:
            # Step 1: Generate unique org slug
            org_slug = generate_org_slug(email, first_name)
            display_name = (
                f"{first_name}'s Workspace" if first_name else 'My Workspace'
            )

            logger.info(f'Provisioning tenant with slug: {org_slug}')

            # Step 2: Create Keycloak realm
            try:
                tenant_info = await self.keycloak_service.create_tenant(
                    org_slug=org_slug,
                    admin_email=email,
                    admin_password=password,
                    admin_first_name=first_name or 'Admin',
                    admin_last_name=last_name or 'User',
                )
                keycloak_realm_created = True
                logger.info(f'Created Keycloak realm: {tenant_info.realm_name}')
            except TenantAlreadyExistsError:
                # Unlikely due to UUID suffix, but handle gracefully
                logger.warning(
                    f'Tenant slug collision for {org_slug}, retrying with new slug'
                )
                org_slug = generate_org_slug(email, first_name)
                tenant_info = await self.keycloak_service.create_tenant(
                    org_slug=org_slug,
                    admin_email=email,
                    admin_password=password,
                    admin_first_name=first_name or 'Admin',
                    admin_last_name=last_name or 'User',
                )
                keycloak_realm_created = True

            # Step 3: Create database tenant record
            db_tenant = await create_tenant(
                realm_name=tenant_info.realm_name,
                display_name=display_name,
                plan='free',
            )
            tenant_created = True
            logger.info(f'Created database tenant: {db_tenant["id"]}')

            # Step 4: Link user to tenant
            await self._link_user_to_tenant(user_id, db_tenant['id'])
            logger.info(f'Linked user {user_id} to tenant {db_tenant["id"]}')

            # Step 5: Create Kubernetes deployment (if enabled)
            k8s_namespace = None
            k8s_external_url = None
            k8s_internal_url = None
            k8s_created = False

            if self.k8s_service:
                try:
                    k8s_result = await self.k8s_service.provision_instance(
                        user_id=user_id,
                        tenant_id=db_tenant['id'],
                        org_slug=org_slug,
                        tier='free',  # Default tier for new signups
                    )

                    if k8s_result.success:
                        k8s_namespace = k8s_result.namespace
                        k8s_external_url = k8s_result.external_url
                        k8s_internal_url = k8s_result.internal_url
                        k8s_created = True
                        logger.info(
                            f'Created K8s instance for user {user_id}: '
                            f'{k8s_external_url}'
                        )

                        # Store K8s instance info in tenant record
                        await self._update_tenant_k8s_info(
                            tenant_id=db_tenant['id'],
                            namespace=k8s_namespace,
                            external_url=k8s_external_url,
                            internal_url=k8s_internal_url,
                        )
                    else:
                        logger.warning(
                            f'K8s provisioning failed (non-fatal): '
                            f'{k8s_result.error_message}'
                        )
                except Exception as e:
                    logger.warning(f'K8s provisioning error (non-fatal): {e}')

            # Success!
            logger.info(f'Instance provisioning completed for user {user_id}')
            return ProvisioningResult(
                success=True,
                tenant_id=db_tenant['id'],
                realm_name=tenant_info.realm_name,
                k8s_namespace=k8s_namespace,
                k8s_external_url=k8s_external_url,
                k8s_internal_url=k8s_internal_url,
                status=ProvisioningStatus.COMPLETED,
            )

        except Exception as e:
            logger.error(
                f'Instance provisioning failed for user {user_id}: {e}'
            )

            # Rollback in reverse order
            await self._rollback(
                user_id=user_id,
                keycloak_realm_created=keycloak_realm_created,
                tenant_info=tenant_info,
                tenant_created=tenant_created,
                db_tenant=db_tenant,
            )

            return ProvisioningResult(
                success=False,
                error_message=str(e),
                status=ProvisioningStatus.FAILED,
            )

    async def _link_user_to_tenant(self, user_id: str, tenant_id: str) -> None:
        """Link a user to their tenant in the database."""
        pool = await get_pool()
        if not pool:
            raise RuntimeError('Database not available')

        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE users
                SET tenant_id = $1, updated_at = NOW()
                WHERE id = $2
                """,
                tenant_id,
                user_id,
            )

    async def _update_tenant_k8s_info(
        self,
        tenant_id: str,
        namespace: str,
        external_url: str,
        internal_url: str,
    ) -> None:
        """Update tenant record with Kubernetes instance information."""
        pool = await get_pool()
        if not pool:
            return

        async with pool.acquire() as conn:
            # Check if columns exist (graceful degradation)
            try:
                await conn.execute(
                    """
                    UPDATE tenants
                    SET 
                        k8s_namespace = $1,
                        k8s_external_url = $2,
                        k8s_internal_url = $3,
                        updated_at = NOW()
                    WHERE id = $4
                    """,
                    namespace,
                    external_url,
                    internal_url,
                    tenant_id,
                )
            except Exception as e:
                # Columns may not exist yet - log and continue
                logger.warning(
                    f'Could not update tenant K8s info (columns may not exist): {e}'
                )

    async def _rollback(
        self,
        user_id: str,
        keycloak_realm_created: bool,
        tenant_info: Optional[TenantInfo],
        tenant_created: bool,
        db_tenant: Optional[dict],
    ) -> None:
        """
        Rollback provisioning changes in reverse order.

        This implements compensating transactions for the saga pattern.
        """
        logger.warning(f'Rolling back provisioning for user {user_id}')

        # Rollback Step 4: Unlink user from tenant (if linked)
        try:
            pool = await get_pool()
            if pool:
                async with pool.acquire() as conn:
                    await conn.execute(
                        'UPDATE users SET tenant_id = NULL WHERE id = $1',
                        user_id,
                    )
                logger.info(f'Rollback: Unlinked user {user_id} from tenant')
        except Exception as e:
            logger.error(f'Rollback failed: Could not unlink user: {e}')

        # Rollback Step 3: Delete database tenant
        if tenant_created and db_tenant:
            try:
                pool = await get_pool()
                if pool:
                    async with pool.acquire() as conn:
                        await conn.execute(
                            'DELETE FROM tenants WHERE id = $1',
                            db_tenant['id'],
                        )
                    logger.info(
                        f'Rollback: Deleted database tenant {db_tenant["id"]}'
                    )
            except Exception as e:
                logger.error(f'Rollback failed: Could not delete tenant: {e}')

        # Rollback Step 2: Delete Keycloak realm
        if keycloak_realm_created and tenant_info:
            try:
                await self.keycloak_service.delete_tenant(
                    tenant_info.realm_name
                )
                logger.info(
                    f'Rollback: Deleted Keycloak realm {tenant_info.realm_name}'
                )
            except Exception as e:
                logger.error(
                    f'Rollback failed: Could not delete Keycloak realm: {e}'
                )

        logger.info(f'Rollback completed for user {user_id}')


# Global service instance
provisioning_service = InstanceProvisioningService()


async def provision_instance_for_new_user(
    user_id: str,
    email: str,
    password: str,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
) -> ProvisioningResult:
    """
    Convenience function to provision an instance for a new user.

    This is the main entry point to be called from user registration.
    """
    return await provisioning_service.provision_instance_for_user(
        user_id=user_id,
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
    )
