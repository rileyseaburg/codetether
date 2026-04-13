"""Git credential broker for GitHub App-backed workspaces."""

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .auth import installation_token

github_git_credentials_router = APIRouter(prefix='/v1/agent', tags=['agent'])


class GitCredentialRequest(BaseModel):
    operation: str = 'get'
    protocol: Optional[str] = None
    host: Optional[str] = None
    path: Optional[str] = None


@github_git_credentials_router.post('/workspaces/{workspace_id}/git/credentials')
async def issue_git_credentials(workspace_id: str, request: GitCredentialRequest):
    """Mint short-lived GitHub credentials for the worker helper."""
    from .. import database as db
    from ..git_service import get_git_credentials

    workspace = await db.db_get_workspace(workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail='Workspace not found')
    credentials = await get_git_credentials(workspace_id)
    if credentials and credentials.get('token'):
        return {'username': 'x-access-token', 'password': credentials['token'], 'expires_at': credentials.get('expires_at'), 'token_type': credentials.get('token_type', 'pat'), 'host': request.host, 'path': request.path}
    github_app = (((workspace.get('agent_config') or {}).get('git_auth') or {}).get('github_app') or {})
    installation_id = github_app.get('installation_id')
    if not installation_id:
        raise HTTPException(status_code=404, detail='No Git credentials available for workspace')
    token, expires_at = await installation_token(int(installation_id))
    return {'username': 'x-access-token', 'password': token, 'expires_at': expires_at, 'token_type': 'github_app', 'host': request.host, 'path': request.path}
