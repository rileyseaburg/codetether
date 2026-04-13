import logging
import uuid

from fastapi import HTTPException

from .. import database as db
from ..database import get_tenant_by_id
from ..keycloak_auth import UserSession
from ..vm_workspace_provisioner import VMWorkspaceSpec, vm_workspace_provisioner
from .common import ensure_tenant_access
from .requests import TenantVMWorkspaceDeploymentRequest
from .responses import TenantVMWorkspaceDeploymentResponse, TenantVMWorkspaceState

logger = logging.getLogger(__name__)


async def provision_vm_workspace(
    tenant_id: str,
    user: UserSession,
    payload: TenantVMWorkspaceDeploymentRequest,
) -> TenantVMWorkspaceDeploymentResponse:
    if not await get_tenant_by_id(tenant_id):
        raise HTTPException(status_code=404, detail='Tenant not found')
    ensure_tenant_access(user, tenant_id)
    workspace_id = str(uuid.uuid4())[:8]
    spec = VMWorkspaceSpec(
        cpu_cores=payload.cpu_cores,
        memory=payload.memory,
        disk_size=payload.disk_size,
        image=payload.image or VMWorkspaceSpec().image,
        ssh_public_key=payload.ssh_public_key or '',
        ssh_user=payload.ssh_user,
    )
    result = await vm_workspace_provisioner.provision_workspace_vm(
        workspace_id=workspace_id,
        workspace_name=payload.name,
        tenant_id=tenant_id,
        spec=spec,
    )
    if not result.success:
        raise HTTPException(status_code=502, detail=result.error_message)
    workspace = _workspace_record(workspace_id, tenant_id, payload, result, spec)
    if not await db.db_upsert_workspace(workspace, tenant_id=tenant_id):
        raise HTTPException(status_code=500, detail='Failed to persist workspace')
    await _hydrate_bridge(workspace)
    return TenantVMWorkspaceDeploymentResponse(
        tenant_id=tenant_id,
        deployment=_workspace_state(workspace),
    )


def _workspace_record(workspace_id, tenant_id, payload, result, spec):
    return {
        'id': workspace_id,
        'tenant_id': tenant_id,
        'name': payload.name,
        'path': payload.path,
        'description': payload.description,
        'status': 'active',
        'agent_config': {
            'workspace_runtime': 'vm',
            'vm_provider': 'kubevirt',
            'vm_name': result.vm_name,
            'vm_namespace': result.namespace,
            'vm_status': result.status,
            'vm_workspace_pvc': result.pvc_name,
            'vm_ssh_service': result.ssh_service_name,
            'vm_ssh_host': result.ssh_host,
            'vm_ssh_port': result.ssh_port,
            'vm_spec': {
                'cpu_cores': spec.cpu_cores,
                'memory': spec.memory,
                'disk_size': spec.disk_size,
                'image': spec.image,
            },
        },
    }


def _workspace_state(workspace):
    config = workspace.get('agent_config') or {}
    return TenantVMWorkspaceState(
        workspace_id=workspace['id'],
        name=workspace['name'],
        path=workspace['path'],
        status=workspace.get('status') or 'active',
        driver=str(config.get('vm_provider') or 'kubevirt'),
        vm_name=config.get('vm_name'),
        vm_namespace=config.get('vm_namespace'),
        vm_status=config.get('vm_status'),
        vm_ssh_host=config.get('vm_ssh_host'),
        vm_ssh_port=config.get('vm_ssh_port'),
    )


async def _hydrate_bridge(workspace):
    try:
        from ..monitor_api import get_agent_bridge

        bridge = get_agent_bridge()
        registered = await bridge.register_workspace(
            name=workspace['name'],
            path=workspace['path'],
            description=workspace.get('description') or '',
            agent_config=workspace.get('agent_config') or {},
            workspace_id=workspace['id'],
        )
        workspace.update(registered.to_dict())
    except Exception as exc:
        logger.warning('VM workspace bridge hydration failed: %s', exc)
