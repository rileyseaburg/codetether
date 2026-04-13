from fastapi import APIRouter, Depends

from ..keycloak_auth import UserSession, require_admin
from .dedicated import provision_dedicated_instance
from .listing import list_tenant_deployments
from .requests import (
    DedicatedTenantDeploymentRequest,
    TenantVMWorkspaceDeploymentRequest,
)
from .responses import (
    DedicatedTenantDeploymentResponse,
    TenantDeploymentListResponse,
    TenantVMWorkspaceDeploymentResponse,
)
from .vm import provision_vm_workspace

router = APIRouter(prefix='/v1/tenants', tags=['tenants'])


@router.post(
    '/{tenant_id}/deployments/dedicated-instance',
    response_model=DedicatedTenantDeploymentResponse,
    status_code=201,
)
async def deploy_dedicated_instance(
    tenant_id: str,
    payload: DedicatedTenantDeploymentRequest,
    user: UserSession = Depends(require_admin),
):
    return await provision_dedicated_instance(tenant_id, user, payload)


@router.post(
    '/{tenant_id}/deployments/workspace-vm',
    response_model=TenantVMWorkspaceDeploymentResponse,
    status_code=201,
)
async def deploy_workspace_vm(
    tenant_id: str,
    payload: TenantVMWorkspaceDeploymentRequest,
    user: UserSession = Depends(require_admin),
):
    return await provision_vm_workspace(tenant_id, user, payload)


@router.get('/{tenant_id}/deployments', response_model=TenantDeploymentListResponse)
async def get_tenant_deployments(
    tenant_id: str,
    user: UserSession = Depends(require_admin),
):
    return await list_tenant_deployments(tenant_id, user)
