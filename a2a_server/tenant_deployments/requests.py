from typing import Optional, Literal

from pydantic import BaseModel, Field


class DedicatedTenantDeploymentRequest(BaseModel):
    tier: Literal['free', 'pro', 'agency', 'enterprise'] = 'free'
    org_slug: Optional[str] = Field(default=None, description='Override slug')
    user_id: Optional[str] = Field(
        default=None,
        description='Execution owner override; defaults to authenticated user',
    )


class TenantVMWorkspaceDeploymentRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    path: str = Field(default='/workspace', min_length=1, max_length=255)
    description: str = Field(default='', max_length=500)
    cpu_cores: int = Field(default=2, ge=1, le=64)
    memory: str = Field(default='8Gi', min_length=2, max_length=32)
    disk_size: str = Field(default='30Gi', min_length=2, max_length=32)
    image: Optional[str] = Field(default=None, max_length=512)
    ssh_public_key: Optional[str] = Field(default=None, max_length=4096)
    ssh_user: str = Field(default='coder', min_length=1, max_length=64)
