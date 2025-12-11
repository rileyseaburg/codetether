"""
Authentication API endpoints for A2A Server.

Provides REST endpoints for:
- User login/logout
- Token refresh
- Session management
- User-codebase associations
- Cross-device sync
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from .keycloak_auth import (
    keycloak_auth,
    get_current_user,
    require_auth,
    UserSession,
    UserCodebaseAssociation,
    UserAgentSession,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/v1/auth', tags=['Authentication'])


# Request/Response Models


class LoginRequest(BaseModel):
    username: str
    password: str
    device_id: Optional[str] = None
    device_name: Optional[str] = None
    device_type: Optional[str] = None


class LoginResponse(BaseModel):
    access_token: str = Field(..., alias='accessToken')
    refresh_token: Optional[str] = Field(None, alias='refreshToken')
    expires_at: str = Field(..., alias='expiresAt')
    session: Dict[str, Any]

    class Config:
        populate_by_name = True


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    access_token: str = Field(..., alias='accessToken')
    refresh_token: Optional[str] = Field(None, alias='refreshToken')
    expires_at: str = Field(..., alias='expiresAt')
    session: Dict[str, Any]

    class Config:
        populate_by_name = True


class LogoutRequest(BaseModel):
    session_id: str


class AuthStatusResponse(BaseModel):
    available: bool
    keycloak_url: str
    realm: str
    client_id: str


class CodebaseAssociationRequest(BaseModel):
    codebase_id: str
    role: str = 'owner'


class AgentSessionRequest(BaseModel):
    codebase_id: str
    agent_type: str = 'build'
    device_id: Optional[str] = None


# Endpoints


@router.get('/status', response_model=AuthStatusResponse)
async def get_auth_status():
    """Check if authentication service is available."""
    return AuthStatusResponse(
        available=True,
        keycloak_url=keycloak_auth.keycloak_url,
        realm=keycloak_auth.realm,
        client_id=keycloak_auth.client_id,
    )


@router.post('/login', response_model=LoginResponse)
async def login(request: LoginRequest):
    """Authenticate user with username and password."""
    try:
        device_info = {}
        if request.device_id:
            device_info['device_id'] = request.device_id
        if request.device_name:
            device_info['device_name'] = request.device_name
        if request.device_type:
            device_info['device_type'] = request.device_type

        session = await keycloak_auth.authenticate_password(
            username=request.username,
            password=request.password,
            device_info=device_info,
        )

        return LoginResponse(
            accessToken=session.access_token,
            refreshToken=session.refresh_token,
            expiresAt=session.expires_at.isoformat(),
            session={
                'userId': session.user_id,
                'sessionId': session.session_id,
                'email': session.email,
                'username': session.username,
                'name': session.name,
                'roles': session.roles,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Login error: {e}')
        raise HTTPException(status_code=500, detail=str(e))


@router.post('/refresh', response_model=RefreshResponse)
async def refresh_token(request: RefreshRequest):
    """Refresh an access token using refresh token."""
    try:
        session = await keycloak_auth.refresh_session(request.refresh_token)

        return RefreshResponse(
            accessToken=session.access_token,
            refreshToken=session.refresh_token,
            expiresAt=session.expires_at.isoformat(),
            session={
                'userId': session.user_id,
                'sessionId': session.session_id,
                'email': session.email,
                'username': session.username,
                'name': session.name,
                'roles': session.roles,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Token refresh error: {e}')
        raise HTTPException(status_code=500, detail=str(e))


@router.post('/logout')
async def logout(request: LogoutRequest):
    """Logout and invalidate session."""
    await keycloak_auth.logout(request.session_id)
    return {'success': True, 'message': 'Logged out successfully'}


@router.get('/me')
async def get_current_user_info(user: UserSession = Depends(require_auth)):
    """Get current authenticated user info."""
    return {
        'userId': user.user_id,
        'sessionId': user.session_id,
        'email': user.email,
        'username': user.username,
        'name': user.name,
        'roles': user.roles,
        'expiresAt': user.expires_at.isoformat(),
    }


@router.get('/sync')
async def get_sync_state(
    user_id: str = Query(..., description='User ID to sync'),
    user: Optional[UserSession] = Depends(get_current_user),
):
    """Get synchronized state across all devices for a user."""
    # Allow if authenticated user matches or no auth required for their own data
    if user and user.user_id != user_id:
        raise HTTPException(
            status_code=403, detail="Cannot access other user's sync state"
        )

    return keycloak_auth.sync_session_state(user_id)


# User-Codebase Associations


@router.get('/user/{user_id}/codebases')
async def get_user_codebases(
    user_id: str,
    user: Optional[UserSession] = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """Get all codebases associated with a user."""
    if user and user.user_id != user_id:
        raise HTTPException(
            status_code=403, detail="Cannot access other user's codebases"
        )

    associations = keycloak_auth.get_user_codebases(user_id)
    return [a.to_dict() for a in associations]


@router.post('/user/{user_id}/codebases')
async def associate_codebase(
    user_id: str,
    request: CodebaseAssociationRequest,
    user: UserSession = Depends(require_auth),
):
    """Associate a codebase with a user."""
    if user.user_id != user_id:
        raise HTTPException(
            status_code=403, detail="Cannot modify other user's codebases"
        )

    # Note: In a real implementation, we'd look up codebase details
    association = keycloak_auth.associate_codebase(
        user_id=user_id,
        codebase_id=request.codebase_id,
        codebase_name=request.codebase_id,  # Would be fetched from codebase
        codebase_path='',  # Would be fetched from codebase
        role=request.role,
    )

    return {'success': True, 'association': association.to_dict()}


@router.delete('/user/{user_id}/codebases/{codebase_id}')
async def remove_codebase_association(
    user_id: str,
    codebase_id: str,
    user: UserSession = Depends(require_auth),
):
    """Remove a codebase association from a user."""
    if user.user_id != user_id:
        raise HTTPException(
            status_code=403, detail="Cannot modify other user's codebases"
        )

    removed = keycloak_auth.remove_codebase_association(user_id, codebase_id)
    return {'success': removed}


# Agent Sessions


@router.get('/user/{user_id}/agent-sessions')
async def get_user_agent_sessions(
    user_id: str,
    user: Optional[UserSession] = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """Get all agent sessions for a user."""
    if user and user.user_id != user_id:
        raise HTTPException(
            status_code=403, detail="Cannot access other user's sessions"
        )

    sessions = keycloak_auth.get_user_agent_sessions(user_id)
    return [s.to_dict() for s in sessions]


@router.post('/user/{user_id}/agent-sessions')
async def create_agent_session(
    user_id: str,
    codebase_id: str = Query(...),
    agent_type: str = Query('build'),
    device_id: Optional[str] = Query(None),
    user: UserSession = Depends(require_auth),
):
    """Create a new agent session for a user."""
    if user.user_id != user_id:
        raise HTTPException(
            status_code=403, detail='Cannot create session for other user'
        )

    session = keycloak_auth.create_agent_session(
        user_id=user_id,
        codebase_id=codebase_id,
        agent_type=agent_type,
        device_id=device_id,
    )

    return {'success': True, 'session': session.to_dict()}


@router.delete('/user/{user_id}/agent-sessions/{session_id}')
async def close_agent_session(
    user_id: str,
    session_id: str,
    user: UserSession = Depends(require_auth),
):
    """Close an agent session."""
    if user.user_id != user_id:
        raise HTTPException(
            status_code=403, detail="Cannot close other user's session"
        )

    keycloak_auth.close_agent_session(session_id)
    return {'success': True}


# Session management


@router.get('/sessions')
async def get_active_sessions(user: UserSession = Depends(require_auth)):
    """Get all active sessions for current user."""
    sessions = keycloak_auth.get_active_sessions_for_user(user.user_id)
    return {
        'sessions': [s.to_dict() for s in sessions],
        'count': len(sessions),
    }


@router.delete('/sessions/{session_id}')
async def invalidate_session(
    session_id: str,
    user: UserSession = Depends(require_auth),
):
    """Invalidate a specific session."""
    target_session = await keycloak_auth.get_session(session_id)
    if not target_session:
        raise HTTPException(status_code=404, detail='Session not found')

    if target_session.user_id != user.user_id:
        raise HTTPException(
            status_code=403, detail="Cannot invalidate other user's session"
        )

    await keycloak_auth.logout(session_id)
    return {'success': True}
