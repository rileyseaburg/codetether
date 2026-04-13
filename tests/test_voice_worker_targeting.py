import json
import os

import pytest

os.environ.setdefault(
    'DATABASE_URL',
    'postgresql://postgres:postgres@localhost:5432/a2a_server',
)

from a2a_server import monitor_api


class _BridgeStub:
    public_url = 'wss://live.example.test'

    def __init__(self):
        self.created_room_metadata = None
        self.dispatched_metadata = None

    async def create_room(self, room_name: str, metadata=None, **_kwargs):
        self.created_room_metadata = metadata
        return {'name': room_name}

    async def dispatch_agent(self, room_name: str, agent_name: str, metadata=None):
        self.dispatched_metadata = json.loads(metadata or '{}')
        return {'id': 'dispatch-1', 'room': room_name, 'agent_name': agent_name}

    def mint_access_token(self, **_kwargs):
        return 'token-123'


@pytest.mark.asyncio
async def test_create_voice_session_preserves_workspace_and_worker_target(monkeypatch):
    bridge = _BridgeStub()
    monkeypatch.setattr(monitor_api, 'get_livekit_bridge', lambda: bridge)

    response = await monitor_api.create_voice_session(
        monitor_api.VoiceSessionRequest(
            workspace_id='ws-voice-1',
            worker_id='wrk-target-1',
            user_id='user-1',
        )
    )

    assert response.livekit_url == 'wss://live.example.test'
    assert bridge.created_room_metadata == {
        'voice': '960f89fc',
        'mode': 'chat',
        'playback_style': 'verbatim',
        'workspace_id': 'ws-voice-1',
        'codebase_id': 'ws-voice-1',
        'session_id': None,
        'user_id': 'user-1',
        'worker_id': 'wrk-target-1',
        'target_worker_id': 'wrk-target-1',
    }
    assert bridge.dispatched_metadata == bridge.created_room_metadata
