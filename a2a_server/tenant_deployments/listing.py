from fastapi import HTTPException

from .. import database as db
from ..database import get_tenant_by_id
from ..keycloak_auth import UserSession
from ..vm_workspace_provisioner import vm_workspace_provisioner
from .common import ensure_tenant_access, org_slug_from_tenant
from .responses import (
    DedicatedTenantDeploymentState,
    TenantDeploymentListResponse,
    TenantVMWorkspaceState,
)


async def list_tenant_deployments(
    tenant_id: str,
    user: UserSession,
) -> TenantDeploymentListResponse:
    tenant = await get_tenant_by_id(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail='Tenant not found')
    ensure_tenant_access(user, tenant_id)
    dedicated = _dedicated_state(tenant)
    workspaces = await db.db_list_workspaces(tenant_id=tenant_id)
    return TenantDeploymentListResponse(
        tenant_id=tenant_id,
        dedicated_instance=dedicated,
        workspace_vms=await _vm_states(workspaces),
    )


def _dedicated_state(tenant):
    if not tenant.get('k8s_namespace'):
        return None
    return DedicatedTenantDeploymentState(
        org_slug=org_slug_from_tenant(tenant),
        namespace=tenant['k8s_namespace'],
        external_url=tenant.get('k8s_external_url'),
        internal_url=tenant.get('k8s_internal_url'),
        plan=tenant.get('plan') or 'free',
        status='completed',
    )


async def _vm_states(workspaces):
    states = []
    for workspace in workspaces:
        config = workspace.get('agent_config') or {}
        if config.get('workspace_runtime') != 'vm':
            continue
        vm_status = config.get('vm_status')
        if config.get('vm_name'):
            vm_status = await vm_workspace_provisioner.get_vm_status(config['vm_name']) or vm_status
        states.append(
            TenantVMWorkspaceState(
                workspace_id=workspace['id'],
                name=workspace['name'],
                path=workspace['path'],
                status=workspace.get('status') or 'active',
                driver=str(config.get('vm_provider') or 'kubevirt'),
                vm_name=config.get('vm_name'),
                vm_namespace=config.get('vm_namespace'),
                vm_status=vm_status,
                vm_ssh_host=config.get('vm_ssh_host'),
                vm_ssh_port=config.get('vm_ssh_port'),
            )
        )
    return states
