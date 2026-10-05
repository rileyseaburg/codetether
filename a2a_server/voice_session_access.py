"""Authenticated ownership for LiveKit voice rooms, shared across replicas.

Room metadata, not process-local state or a client-provided participant ID, is
the source of truth. Unowned legacy rooms deliberately fail closed.
"""

import json

from typing import Any

from fastapi import HTTPException


def voice_owner(user: dict[str, Any]) -> dict[str, Any]:
    """Bind the participant to the verified platform principal and tenant."""
    identity = user.get('user_id') or user.get('id')
    if not isinstance(identity, str) or not identity.strip():
        raise HTTPException(status_code=401, detail='Authentication required')
    return {
        'user_id': identity,
        'tenant_id': user.get('tenant_id') or None,
        'ownership_version': 1,
    }


async def owned_voice_room(bridge, room_name: str, user: dict[str, Any]):
    """Read only rooms owned by this caller; conceal other tenants' rooms."""
    owner = voice_owner(user)
    try:
        room = await bridge.get_room_info(room_name, strict=True)
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail='Voice session service unavailable'
        ) from exc
    metadata = room.get('metadata') if room else None
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except (ValueError, TypeError):
            metadata = None
    if not isinstance(metadata, dict) or any(
        metadata.get(key) != value for key, value in owner.items()
    ):
        raise HTTPException(status_code=404, detail='Voice session not found')
    return room, metadata


async def voice_agent_state(bridge, room_name: str) -> str:
    """Read worker telemetry, never infer speech from room occupancy.

    Only LiveKit's server-assigned AGENT participant kind is authoritative;
    browser identities and user-editable metadata/attributes are not.
    """
    participants = await bridge.list_participants(room_name, strict=True)
    agents = [p for p in participants if p.get('kind') == 'agent']
    if not agents:
        return 'idle'
    if len(agents) != 1:
        return 'unknown'
    state = agents[0].get('attributes', {}).get('lk.agent.state')
    if state in (
        'idle',
        'listening',
        'thinking',
        'speaking',
        'tool_calling',
        'tool_complete',
        'error',
    ):
        return state
    return 'unknown'
