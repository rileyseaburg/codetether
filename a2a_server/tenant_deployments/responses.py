from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class DedicatedTenantDeploymentState(BaseModel):
    runtime: Literal['container'] = 'container'
    driver: Literal['kubernetes'] = 'kubernetes'
    org_slug: str
    namespace: str
    external_url: Optional[str] = None
    internal_url: Optional[str] = None
    plan: str
    status: str


class TenantVMWorkspaceState(BaseModel):
    runtime: Literal['vm'] = 'vm'
    driver: str = 'kubevirt'
    workspace_id: str
    name: str
    path: str
    status: str
    vm_name: Optional[str] = None
    vm_namespace: Optional[str] = None
    vm_status: Optional[str] = None
    vm_ssh_host: Optional[str] = None
    vm_ssh_port: Optional[int] = None


class DedicatedTenantDeploymentResponse(BaseModel):
    tenant_id: str
    deployment: DedicatedTenantDeploymentState


class TenantVMWorkspaceDeploymentResponse(BaseModel):
    tenant_id: str
    deployment: TenantVMWorkspaceState


class TenantDeploymentListResponse(BaseModel):
    tenant_id: str
    dedicated_instance: Optional[DedicatedTenantDeploymentState] = None
    workspace_vms: List[TenantVMWorkspaceState] = Field(default_factory=list)
