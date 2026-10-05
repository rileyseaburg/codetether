"""Authoritative tenant-scoped workspace access for durable session recovery."""

from fastapi import APIRouter, Depends, HTTPException

from . import database as db
from .policy import enforce_policy, require_permission

router = APIRouter()


async def authorize_workspace(workspace_id: str, user: dict) -> dict:
    """Require a recorded tenant owner, even when database RLS is disabled."""
    workspace = await db.db_get_workspace(workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail='Workspace not found')
    tenant_id = user.get('tenant_id')
    owner = workspace.get('tenant_id')
    if not tenant_id or not owner or tenant_id != owner:
        raise HTTPException(status_code=403, detail='Workspace access denied')
    await enforce_policy(user, 'sessions:write', {'tenant_id': owner})
    path = workspace.get('path')
    if not isinstance(path, str) or not path.strip():
        raise HTTPException(status_code=503, detail='Workspace path unavailable')
    return {'id': workspace_id, 'path': path}


@router.post('/workspaces/{workspace_id}/session-access')
async def session_access(
    workspace_id: str,
    user: dict = Depends(require_permission('sessions:write')),
) -> dict:
    """Return a workspace binding only for a verified authorized principal."""
    return await authorize_workspace(workspace_id, user)
