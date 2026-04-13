from fastapi import HTTPException

from ..database import get_tenant_by_id, update_tenant
from ..k8s_provisioning import k8s_provisioning_service
from ..keycloak_auth import UserSession
from .common import ensure_tenant_access, org_slug_from_tenant
from .requests import DedicatedTenantDeploymentRequest
from .responses import (
    DedicatedTenantDeploymentResponse,
    DedicatedTenantDeploymentState,
)


async def provision_dedicated_instance(
    tenant_id: str,
    user: UserSession,
    payload: DedicatedTenantDeploymentRequest,
) -> DedicatedTenantDeploymentResponse:
    tenant = await get_tenant_by_id(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail='Tenant not found')
    ensure_tenant_access(user, tenant_id)
    org_slug = payload.org_slug or org_slug_from_tenant(tenant)
    result = await k8s_provisioning_service.provision_instance(
        user_id=payload.user_id or user.user_id,
        tenant_id=tenant_id,
        org_slug=org_slug,
        tier=payload.tier,
    )
    if not result.success:
        raise HTTPException(status_code=502, detail=result.error_message)
    tenant = await update_tenant(
        tenant_id,
        plan=payload.tier,
        k8s_namespace=result.namespace,
        k8s_external_url=result.external_url,
        k8s_internal_url=result.internal_url,
    )
    return DedicatedTenantDeploymentResponse(
        tenant_id=tenant_id,
        deployment=DedicatedTenantDeploymentState(
            org_slug=org_slug,
            namespace=result.namespace or '',
            external_url=result.external_url,
            internal_url=result.internal_url,
            plan=tenant.get('plan') or payload.tier,
            status=getattr(result.status, 'value', str(result.status)),
        ),
    )
