"""Mocked-local voice API regressions; no LiveKit/network services used."""

import json
import os

from http import HTTPStatus
from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from fastapi import FastAPI, HTTPException
from livekit import api


# Import-time configuration only; database operations in these tests are mocked.
os.environ.setdefault(
    'DATABASE_URL', 'postgresql://test:test@localhost/voice_test'
)

from a2a_server import monitor_api, policy
from a2a_server.livekit_bridge import LiveKitBridge
from a2a_server.voice_session_access import owned_voice_room, voice_owner


OWNER = {'user_id': 'alice', 'tenant_id': 'tenant-a', 'roles': ['editor']}


@pytest.fixture
def bridge(monkeypatch):
    fake = Mock(
        public_url='wss://voice.example.test',
        create_room=AsyncMock(),
        dispatch_agent=AsyncMock(return_value={'id': 'dispatch-test'}),
        delete_room=AsyncMock(),
        list_participants=AsyncMock(return_value=[]),
        mint_access_token=Mock(return_value='scoped-test-token'),
        get_room_info=AsyncMock(
            return_value={
                'metadata': json.dumps(voice_owner(OWNER)),
                'num_participants': 0,
            }
        ),
    )
    monkeypatch.setattr(monitor_api, 'get_livekit_bridge', lambda: fake)
    monkeypatch.setattr(
        monitor_api.db,
        'db_get_workspace',
        AsyncMock(
            return_value={
                'id': 'workspace-a',
                'tenant_id': 'tenant-a',
                'worker_id': 'worker-a',
            }
        ),
    )
    monkeypatch.setattr(
        monitor_api.db,
        'db_get_session',
        AsyncMock(
            return_value={
                'id': 'session-a',
                'workspace_id': 'workspace-a',
            }
        ),
    )
    return fake


@pytest.fixture
def voice_request():
    return monitor_api.VoiceSessionRequest(
        voice=monitor_api.AVAILABLE_VOICES[0]['id']
    )


@pytest.mark.parametrize('user', [{}, {'user_id': ''}, {'id': None}])
def test_owner_requires_authenticated_identity(user):
    with pytest.raises(HTTPException) as exc:
        voice_owner(user)
    assert exc.value.status_code == HTTPStatus.UNAUTHORIZED


def test_owner_accepts_verified_id_alias():
    assert voice_owner({'id': 'alice'}) == {
        'user_id': 'alice',
        'tenant_id': None,
        'ownership_version': 1,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'metadata',
    [
        None,
        '',
        'not-json',
        '[]',
        'null',
        '{}',
        json.dumps({'user_id': 'alice', 'tenant_id': 'tenant-a'}),
        json.dumps({**voice_owner(OWNER), 'user_id': 'bob'}),
        json.dumps({**voice_owner(OWNER), 'tenant_id': 'tenant-b'}),
    ],
)
async def test_unowned_or_foreign_rooms_are_not_disclosed(bridge, metadata):
    bridge.get_room_info.return_value = {'metadata': metadata}
    with pytest.raises(HTTPException) as exc:
        await owned_voice_room(bridge, 'room', OWNER)
    assert exc.value.status_code == HTTPStatus.NOT_FOUND
    assert exc.value.detail == 'Voice session not found'


@pytest.mark.asyncio
async def test_missing_room(bridge):
    bridge.get_room_info.return_value = None
    with pytest.raises(HTTPException) as exc:
        await owned_voice_room(bridge, 'room', OWNER)
    assert exc.value.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_creation_binds_token_and_metadata_to_verified_owner(
    bridge, voice_request
):
    voice_request.user_id = 'forged-identity'
    voice_request.workspace_id = 'workspace-a'
    voice_request.worker_id = 'worker-a'
    result = await monitor_api.create_voice_session(voice_request, OWNER)
    metadata = bridge.create_room.call_args.kwargs['metadata']
    assert metadata['user_id'] == result.user_id == 'alice'
    assert metadata['tenant_id'] == 'tenant-a'
    assert metadata['workspace_id'] == metadata['codebase_id'] == 'workspace-a'
    assert metadata['target_worker_id'] == 'worker-a'
    assert bridge.mint_access_token.call_args.kwargs['identity'] == 'alice'
    assert result.access_token == 'scoped-test-token'
    assert result.livekit_url == 'wss://voice.example.test'


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'target', ['workspace', 'session', 'worker', 'missing', 'unscoped']
)
async def test_forbidden_execution_targets_do_not_create_rooms(
    bridge, voice_request, target
):
    voice_request.workspace_id = 'workspace-a'
    if target == 'workspace':
        monitor_api.db.db_get_workspace.return_value['tenant_id'] = 'tenant-b'
    elif target == 'session':
        voice_request.session_id = 'session-b'
        monitor_api.db.db_get_session.return_value['workspace_id'] = (
            'workspace-b'
        )
    elif target == 'worker':
        voice_request.worker_id = 'worker-b'
    elif target == 'missing':
        monitor_api.db.db_get_workspace.return_value = None
    else:
        monitor_api.db.db_get_workspace.return_value['tenant_id'] = None
    with pytest.raises(HTTPException) as exc:
        await monitor_api.create_voice_session(voice_request, OWNER)
    assert exc.value.status_code == HTTPStatus.NOT_FOUND
    bridge.create_room.assert_not_awaited()
    bridge.dispatch_agent.assert_not_awaited()


@pytest.mark.asyncio
async def test_session_target_infers_and_authorizes_workspace(
    bridge, voice_request
):
    voice_request.session_id = 'session-a'
    await monitor_api.create_voice_session(voice_request, OWNER)
    monitor_api.db.db_get_workspace.assert_awaited_once_with('workspace-a')
    assert (
        bridge.create_room.call_args.kwargs['metadata']['workspace_id']
        == 'workspace-a'
    )


@pytest.mark.asyncio
async def test_bare_worker_target_rejected(bridge, voice_request):
    voice_request.worker_id = 'worker-a'
    with pytest.raises(HTTPException) as exc:
        await monitor_api.create_voice_session(voice_request, OWNER)
    assert exc.value.status_code == HTTPStatus.BAD_REQUEST
    bridge.create_room.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['dispatch_agent', 'mint_access_token'])
async def test_partial_creation_cleans_up_room(bridge, voice_request, failure):
    getattr(bridge, failure).side_effect = RuntimeError('test failure')
    with pytest.raises(HTTPException) as exc:
        await monitor_api.create_voice_session(voice_request, OWNER)
    assert exc.value.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    bridge.delete_room.assert_awaited_once_with(
        bridge.create_room.call_args.kwargs['room_name']
    )


@pytest.mark.asyncio
async def test_reconnect_ignores_forged_participant_identity(bridge):
    result = await monitor_api.get_voice_session('room', 'mallory', OWNER)
    assert result['user_id'] == 'alice'
    assert result['access_token'] == 'scoped-test-token'
    assert bridge.mint_access_token.call_args.kwargs['identity'] == 'alice'


@pytest.mark.asyncio
async def test_reconnect_token_failure_is_not_success(bridge):
    bridge.mint_access_token.side_effect = RuntimeError('test token failure')
    with pytest.raises(HTTPException) as exc:
        await monitor_api.get_voice_session('room', 'alice', OWNER)
    assert exc.value.status_code == HTTPStatus.SERVICE_UNAVAILABLE


@pytest.mark.asyncio
@pytest.mark.parametrize('action', ['get', 'state', 'delete'])
async def test_cross_tenant_actions_do_not_mint_or_delete(bridge, action):
    outsider = {**OWNER, 'tenant_id': 'tenant-b'}
    with pytest.raises(HTTPException) as exc:
        if action == 'get':
            await monitor_api.get_voice_session('room', 'alice', outsider)
        elif action == 'state':
            await monitor_api.get_voice_session_state('room', outsider)
        else:
            await monitor_api.delete_voice_session('room', outsider)
    assert exc.value.status_code == HTTPStatus.NOT_FOUND
    bridge.delete_room.assert_not_awaited()
    bridge.mint_access_token.assert_not_called()


@pytest.mark.asyncio
async def test_bridge_serializes_sdk_participant_response():
    fake = Mock()
    fake.livekit_api.room.list_participants = AsyncMock(
        return_value=api.ListParticipantsResponse(
            participants=[
                api.ParticipantInfo(
                    identity='worker',
                    kind=api.ParticipantInfo.AGENT,
                    attributes={'lk.agent.state': 'thinking'},
                ),
                api.ParticipantInfo(
                    identity='browser',
                    kind=api.ParticipantInfo.STANDARD,
                    attributes={'lk.agent.state': 'speaking'},
                ),
            ]
        )
    )
    result = await LiveKitBridge.list_participants(fake, 'room', strict=True)
    assert [(p['kind'], p['attributes']) for p in result] == [
        ('agent', {'lk.agent.state': 'thinking'}),
        ('standard', {'lk.agent.state': 'speaking'}),
    ]
    request = fake.livekit_api.room.list_participants.call_args.args[0]
    assert request.room == 'room'


@pytest.mark.asyncio
async def test_bridge_participant_outage_and_empty_room_are_distinct():
    fake = Mock()
    fake.livekit_api.room.list_participants = AsyncMock(
        side_effect=RuntimeError('participant service offline')
    )
    with pytest.raises(RuntimeError, match='participant service offline'):
        await LiveKitBridge.list_participants(fake, 'room', strict=True)
    assert await LiveKitBridge.list_participants(fake, 'room') == []
    fake.livekit_api.room.list_participants.side_effect = None
    fake.livekit_api.room.list_participants.return_value = (
        api.ListParticipantsResponse()
    )
    assert (
        await LiveKitBridge.list_participants(fake, 'room', strict=True) == []
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'participants,expected',
    [
        ([], 'idle'),
        (
            [
                {
                    'kind': 'standard',
                    'identity': 'agent-forged',
                    'attributes': {'lk.agent.state': 'speaking'},
                }
            ],
            'idle',
        ),
        ([{'kind': 'agent', 'attributes': {}}], 'unknown'),
        (
            [{'kind': 'agent', 'attributes': {'lk.agent.state': 'invalid'}}],
            'unknown',
        ),
        ([{'kind': 'agent'}, {'kind': 'agent'}], 'unknown'),
        *[
            (
                [{'kind': 'agent', 'attributes': {'lk.agent.state': state}}],
                state,
            )
            for state in (
                'idle',
                'listening',
                'thinking',
                'speaking',
                'tool_calling',
                'tool_complete',
                'error',
            )
        ],
    ],
)
async def test_owned_room_state(bridge, participants, expected):
    bridge.list_participants.return_value = participants
    # Occupancy and a session ID are not evidence of speech or worker state.
    bridge.get_room_info.return_value = {
        'metadata': json.dumps(
            {**voice_owner(OWNER), 'session_id': 'session-a'}
        ),
        'num_participants': 99,
    }
    assert await monitor_api.get_voice_session_state('room', OWNER) == expected
    bridge.list_participants.assert_awaited_once_with('room', strict=True)


@pytest.mark.asyncio
async def test_state_service_failure_is_unavailable_not_idle(bridge):
    bridge.get_room_info.side_effect = RuntimeError('test service outage')
    with pytest.raises(HTTPException) as exc:
        await monitor_api.get_voice_session_state('room', OWNER)
    assert exc.value.status_code == HTTPStatus.SERVICE_UNAVAILABLE


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'method,path',
    [
        ('POST', '/v1/voice/sessions'),
        ('GET', '/v1/voice/sessions/room'),
        ('GET', '/v1/voice/sessions/room/state'),
        ('DELETE', '/v1/voice/sessions/room'),
    ],
)
async def test_http_routes_require_authentication(
    bridge, voice_request, monkeypatch, method, path
):
    monkeypatch.setattr(policy, '_resolve_user', AsyncMock(return_value=None))
    app = FastAPI()
    app.include_router(monitor_api.voice_router)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url='http://test'
    ) as client:
        response = await client.request(
            method, path, json=voice_request.model_dump()
        )
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    bridge.create_room.assert_not_awaited()
    bridge.delete_room.assert_not_awaited()
    bridge.mint_access_token.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize('action', ['get', 'delete', 'state'])
async def test_room_service_outage_is_not_missing_room(bridge, action):
    bridge.get_room_info.side_effect = RuntimeError('room service outage')
    with pytest.raises(HTTPException) as exc:
        if action == 'get':
            await monitor_api.get_voice_session('room', 'alice', OWNER)
        elif action == 'delete':
            await monitor_api.delete_voice_session('room', OWNER)
        else:
            await monitor_api.get_voice_session_state('room', OWNER)
    assert exc.value.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    bridge.get_room_info.assert_awaited_once_with('room', strict=True)
    bridge.delete_room.assert_not_awaited()
    bridge.mint_access_token.assert_not_called()


@pytest.mark.asyncio
async def test_bridge_strict_lookup_distinguishes_outage_from_absence():
    fake = Mock(livekit_api=Mock(room=Mock(list_rooms=AsyncMock())))
    fake.livekit_api.room.list_rooms.side_effect = RuntimeError(
        'service outage'
    )
    with pytest.raises(RuntimeError, match='service outage'):
        await LiveKitBridge.get_room_info(fake, 'room', strict=True)
    # Existing non-voice callers retain the best-effort compatibility contract.
    assert await LiveKitBridge.get_room_info(fake, 'room') is None
    fake.livekit_api.room.list_rooms.side_effect = None
    fake.livekit_api.room.list_rooms.return_value = Mock(rooms=[])
    assert await LiveKitBridge.get_room_info(fake, 'room', strict=True) is None


@pytest.mark.asyncio
async def test_participant_service_failure_is_not_idle(bridge):
    bridge.list_participants.side_effect = RuntimeError(
        'participant service offline'
    )
    with pytest.raises(HTTPException) as exc:
        await monitor_api.get_voice_session_state('room', OWNER)
    assert exc.value.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    bridge.mint_access_token.assert_not_called()
    bridge.delete_room.assert_not_awaited()
