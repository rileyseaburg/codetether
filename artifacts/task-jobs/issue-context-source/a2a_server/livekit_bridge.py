"""
LiveKit Bridge Module for A2A Server

This module handles all communication with LiveKit services, including:
- Creating rooms via LiveKit SDK
- Minting short-lived access tokens
- Mapping A2A roles to LiveKit grants
- Validating A2A authentication before minting tokens
"""

import os
import json
import time
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

try:
    from livekit import api

    LIVEKIT_AVAILABLE = True
except ImportError:
    LIVEKIT_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning(
        'LiveKit SDK not installed. LiveKit features will be disabled.'
    )

logger = logging.getLogger(__name__)


class LiveKitBridge:
    """Bridge between A2A server and LiveKit services."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        livekit_url: Optional[str] = None,
        public_url: Optional[str] = None,
    ):
        """Initialize LiveKit bridge with API credentials.

        Args:
            api_key: LiveKit API key (defaults to LIVEKIT_API_KEY env var)
            api_secret: LiveKit API secret (defaults to LIVEKIT_API_SECRET env var)
            livekit_url: LiveKit server URL for API calls (defaults to LIVEKIT_URL env var)
            public_url: Public LiveKit URL for client WebSocket connections (defaults to LIVEKIT_PUBLIC_URL env var)
        """
        if not LIVEKIT_AVAILABLE:
            raise ImportError(
                'LiveKit SDK is not installed. '
                'Install it with: pip install livekit'
            )

        self.api_key = api_key or os.getenv('LIVEKIT_API_KEY')
        self.api_secret = api_secret or os.getenv('LIVEKIT_API_SECRET')
        self.livekit_url = livekit_url or os.getenv(
            'LIVEKIT_URL', 'https://live.quantum-forge.net/'
        )
        # Public URL for client connections (defaults to wss:// version of livekit_url if not set)
        self.public_url = public_url or os.getenv('LIVEKIT_PUBLIC_URL')

        if not self.api_key or not self.api_secret:
            raise ValueError(
                'LiveKit API key and secret must be provided either as parameters '
                'or through LIVEKIT_API_KEY and LIVEKIT_API_SECRET environment variables'
            )

        # Normalize URL - remove trailing slash and ensure http/https
        self.livekit_url = self.livekit_url.rstrip('/')
        if not self.livekit_url.startswith(('http://', 'https://')):
            self.livekit_url = f'https://{self.livekit_url}'

        # Normalize public URL - if not set, derive from livekit_url
        if not self.public_url:
            # Convert http(s):// to wss://
            self.public_url = self.livekit_url.replace(
                'http://', 'wss://'
            ).replace('https://', 'wss://')
        self.public_url = self.public_url.rstrip('/')

        # Initialize LiveKit API client lazily (on first use) to avoid event loop issues
        self._livekit_api = None

        logger.info(
            f'LiveKit bridge initialized with URL: {self.livekit_url}, public URL: {self.public_url}'
        )

    @property
    def livekit_api(self):
        """Lazy initialization of LiveKit API client."""
        if self._livekit_api is None:
            self._livekit_api = api.LiveKitAPI(
                url=self.livekit_url,
                api_key=self.api_key,
                api_secret=self.api_secret,
            )
        return self._livekit_api

    async def create_room(
        self,
        room_name: str,
        metadata: Optional[Dict[str, Any]] = None,
        max_participants: int = 50,
        empty_timeout: int = 300,  # 5 minutes
        departure_timeout: int = 60,  # 1 minute
    ) -> Dict[str, Any]:
        """Create a new LiveKit room using the SDK.

        Args:
            room_name: Unique name for the room
            metadata: Optional metadata to attach to the room
            max_participants: Maximum number of participants allowed
            empty_timeout: Timeout in seconds for empty room
            departure_timeout: Timeout in seconds after last participant leaves

        Returns:
            Dictionary containing room information
        """
        try:
            # Use LiveKit SDK to create room
            room = await self.livekit_api.room.create_room(
                api.CreateRoomRequest(
                    name=room_name,
                    empty_timeout=empty_timeout,
                    departure_timeout=departure_timeout,
                    max_participants=max_participants,
                    metadata=json.dumps(metadata) if metadata else None,
                )
            )

            logger.info(f'Created LiveKit room: {room_name}')

            # Return room info as dictionary
            return {
                'name': room.name,
                'sid': room.sid,
                'empty_timeout': room.empty_timeout,
                'departure_timeout': room.departure_timeout,
                'max_participants': room.max_participants,
                'creation_time': room.creation_time,
                'num_participants': room.num_participants,
                'metadata': room.metadata,
            }

        except Exception as e:
            logger.error(f'Failed to create LiveKit room {room_name}: {e}')
            raise

    async def get_room_info(self, room_name: str) -> Optional[Dict[str, Any]]:
        """Get information about an existing room using the SDK.

        Args:
            room_name: Name of the room to get info for

        Returns:
            Room information dictionary or None if room doesn't exist
        """
        try:
            # Use LiveKit SDK to list rooms
            resp = await self.livekit_api.room.list_rooms(
                api.ListRoomsRequest(names=[room_name])
            )

            rooms = resp.rooms if hasattr(resp, 'rooms') else resp
            if rooms and len(rooms) > 0:
                room = rooms[0]
                return {
                    'name': room.name,
                    'sid': room.sid,
                    'empty_timeout': room.empty_timeout,
                    'departure_timeout': room.departure_timeout,
                    'max_participants': room.max_participants,
                    'creation_time': room.creation_time,
                    'num_participants': room.num_participants,
                    'metadata': room.metadata,
                }
            return None

        except Exception as e:
            logger.error(f'Failed to get room info for {room_name}: {e}')
            return None

    def mint_access_token(
        self,
        identity: str,
        room_name: str,
        a2a_role: str = 'participant',
        metadata: Optional[str] = None,
        ttl_minutes: int = 60,
    ) -> str:
        """Mint a short-lived access token for LiveKit room access using SDK.

        Args:
            identity: Unique identity for the participant
            room_name: Name of the room to join
            a2a_role: A2A role (mapped to LiveKit grants)
            metadata: Optional metadata for the participant
            ttl_minutes: Token time-to-live in minutes

        Returns:
            JWT access token string
        """
        try:
            # Map A2A role to LiveKit video grants
            grants = self._map_a2a_role_to_grants(a2a_role, room_name)

            # Create access token using SDK
            token = api.AccessToken(self.api_key, self.api_secret)
            token.with_identity(identity)
            token.with_name(identity)
            token.with_ttl(timedelta(minutes=ttl_minutes))

            # Set video grants
            token.with_grants(
                api.VideoGrants(
                    room_join=grants.get('roomJoin', True),
                    room=grants.get('room', room_name),
                    room_admin=grants.get('roomAdmin', False),
                    can_publish=grants.get('canPublish', True),
                    can_subscribe=grants.get('canSubscribe', True),
                    can_publish_data=grants.get('canPublishData', True),
                    can_update_own_metadata=grants.get(
                        'canUpdateOwnMetadata', True
                    ),
                    hidden=grants.get('hidden', False),
                    recorder=grants.get('recorder', False),
                )
            )

            if metadata:
                token.with_metadata(metadata)

            access_token_str = token.to_jwt()

            logger.info(
                f'Minted access token for {identity} in room {room_name} with role {a2a_role}'
            )

            return access_token_str

        except Exception as e:
            logger.error(f'Failed to mint access token for {identity}: {e}')
            raise

    def _map_a2a_role_to_grants(
        self, a2a_role: str, room_name: str
    ) -> Dict[str, Any]:
        """Map A2A roles to LiveKit video grants.

        Args:
            a2a_role: A2A role string
            room_name: Room name for scoped permissions

        Returns:
            Dictionary with video grants
        """
        # Define role mappings
        role_mappings = {
            'admin': {
                'roomJoin': True,
                'room': room_name,
                'roomAdmin': True,
                'canPublish': True,
                'canSubscribe': True,
                'canPublishData': True,
                'canUpdateOwnMetadata': True,
                'recorder': True,
            },
            'moderator': {
                'roomJoin': True,
                'room': room_name,
                'roomAdmin': False,
                'canPublish': True,
                'canSubscribe': True,
                'canPublishData': True,
                'canUpdateOwnMetadata': True,
                'recorder': False,
            },
            'publisher': {
                'roomJoin': True,
                'room': room_name,
                'roomAdmin': False,
                'canPublish': True,
                'canSubscribe': True,
                'canPublishData': True,
                'canUpdateOwnMetadata': False,
                'recorder': False,
            },
            'participant': {
                'roomJoin': True,
                'room': room_name,
                'roomAdmin': False,
                'canPublish': True,
                'canSubscribe': True,
                'canPublishData': False,
                'canUpdateOwnMetadata': False,
                'recorder': False,
            },
            'viewer': {
                'roomJoin': True,
                'room': room_name,
                'roomAdmin': False,
                'canPublish': False,
                'canSubscribe': True,
                'canPublishData': False,
                'canUpdateOwnMetadata': False,
                'recorder': False,
            },
        }

        # Default to participant if role not found
        grants = role_mappings.get(
            a2a_role.lower(), role_mappings['participant']
        )

        logger.debug(
            f"Mapped A2A role '{a2a_role}' to LiveKit grants for room {room_name}"
        )

        return grants

    async def dispatch_agent(
        self,
        room_name: str,
        agent_name: str,
        metadata: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a LiveKit agent dispatch for a room.

        Args:
            room_name: Name of the room to dispatch into
            agent_name: LiveKit worker agent name to target
            metadata: Optional dispatch metadata string

        Returns:
            Dictionary with dispatch details
        """
        if not room_name:
            raise ValueError('room_name is required for agent dispatch')
        if not agent_name:
            raise ValueError('agent_name is required for agent dispatch')

        try:
            dispatch = await self.livekit_api.agent_dispatch.create_dispatch(
                api.CreateAgentDispatchRequest(
                    room=room_name,
                    agent_name=agent_name,
                    metadata=metadata or '',
                )
            )

            dispatch_id = getattr(dispatch, 'id', None)
            logger.info(
                f'Created agent dispatch for room {room_name} to agent {agent_name}'
                + (f' (dispatch_id={dispatch_id})' if dispatch_id else '')
            )

            return {
                'id': dispatch_id,
                'room': getattr(dispatch, 'room', room_name),
                'agent_name': getattr(dispatch, 'agent_name', agent_name),
                'metadata': getattr(dispatch, 'metadata', metadata or ''),
            }
        except Exception as e:
            logger.error(
                f'Failed to dispatch agent {agent_name} for room {room_name}: {e}'
            )
            raise

    async def delete_room(self, room_name: str) -> bool:
        """Delete a LiveKit room via SDK API.

        Args:
            room_name: Name of the room to delete

        Returns:
            True if deletion was successful, False otherwise
        """
        try:
            await self.livekit_api.room.delete_room(
                api.DeleteRoomRequest(room=room_name)
            )
            logger.info(f'Deleted LiveKit room: {room_name}')
            return True

        except Exception as e:
            logger.error(f'Failed to delete room {room_name}: {e}')
            return False

    async def list_participants(self, room_name: str) -> List[Dict[str, Any]]:
        """List participants in a room via SDK API.

        Args:
            room_name: Name of the room

        Returns:
            List of participant information dictionaries
        """
        try:
            participants = await self.livekit_api.room.list_participants(
                api.ListParticipantsRequest(room=room_name)
            )
            return [
                {
                    'sid': p.sid,
                    'identity': p.identity,
                    'name': p.name,
                    'state': int(p.state) if p.state is not None else None,
                    'metadata': p.metadata,
                    'joined_at': p.joined_at,
                }
                for p in participants
            ]

        except Exception as e:
            logger.error(
                f'Failed to list participants for room {room_name}: {e}'
            )
            return []

    def generate_join_url(
        self, room_name: str, token: str, base_url: Optional[str] = None
    ) -> str:
        """Generate a join URL for a LiveKit room.

        Args:
            room_name: Name of the room
            token: Access token for the room
            base_url: Base URL for the LiveKit frontend (optional)

        Returns:
            Complete join URL
        """
        if base_url:
            # Use provided base URL (e.g., custom frontend)
            return f'{base_url}?room={room_name}&token={token}'
        else:
            # Use LiveKit server URL with default frontend
            url = self.livekit_url
            if url.startswith('https://'):
                # Keep https for web frontend
                pass
            elif url.startswith('http://'):
                # Keep http for local development
                pass
            else:
                url = f'https://{url}'

            return f'{url}?room={room_name}&token={token}'

    async def close(self):
        """Close LiveKit API client resources."""
        if self._livekit_api is not None:
            await self._livekit_api.aclose()


def create_livekit_bridge() -> Optional[LiveKitBridge]:
    """Create a LiveKit bridge instance if credentials are available.

    Returns:
        LiveKitBridge instance or None if credentials not configured
    """
    try:
        return LiveKitBridge()
    except ValueError as e:
        logger.warning(f'LiveKit bridge not initialized: {e}')
        return None
