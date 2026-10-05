"""LiveKit room-token service for Remote Employee."""

from __future__ import annotations

import json
import os

from datetime import timedelta


try:
    from livekit import api
except ImportError:  # pragma: no cover - handled as an unconfigured service
    api = None


class LiveKitTokens:
    """Issue short-lived, room-scoped participant tokens."""

    def __init__(self):
        self.api_key = os.getenv('LIVEKIT_API_KEY')
        self.api_secret = os.getenv('LIVEKIT_API_SECRET')
        self.url = os.getenv(
            'LIVEKIT_PUBLIC_URL', 'wss://live.quantum-forge.net'
        ).rstrip('/')

    @property
    def configured(self) -> bool:
        return bool(api and self.api_key and self.api_secret)

    def issue(
        self, *, identity: str, room: str, name: str, role: str
    ) -> dict[str, str]:
        if not self.configured:
            raise RuntimeError('LiveKit credentials are not configured')
        token = api.AccessToken(self.api_key, self.api_secret)
        token.with_identity(identity[:128])
        token.with_name(name[:128])
        token.with_ttl(timedelta(minutes=30))
        token.with_grants(
            api.VideoGrants(
                room_join=True,
                room=room,
                can_publish=True,
                can_subscribe=True,
                can_publish_data=True,
                can_update_own_metadata=True,
            )
        )
        token.with_metadata(
            json.dumps({'role': role, 'product': 'remote-employee'})
        )
        return {'url': self.url, 'room': room, 'token': token.to_jwt()}
