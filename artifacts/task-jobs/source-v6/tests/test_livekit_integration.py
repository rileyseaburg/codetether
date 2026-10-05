"""
Integration tests for LiveKit A2A integration
"""
import pytest
import asyncio
import httpx
from unittest.mock import patch, AsyncMock
from a2a_server.livekit_bridge import LiveKitBridge
from a2a_server.enhanced_agents import MediaAgent
from a2a_server.models import Message, Part


class TestLiveKitBridge:
    """Test LiveKit bridge functionality."""

    def test_bridge_initialization_without_credentials(self):
        """Test that bridge initialization fails without credentials."""
        with pytest.raises(ValueError):
            LiveKitBridge()

    def test_bridge_initialization_with_credentials(self):
        """Test successful bridge initialization."""
        bridge = LiveKitBridge(
            api_key="test_key",
            api_secret="test_secret",
            livekit_url="https://live.quantum-forge.net"
        )
        assert bridge.api_key == "test_key"
        assert bridge.api_secret == "test_secret"
        assert bridge.livekit_url == "https://live.quantum-forge.net"

    def test_role_mapping(self):
        """Test A2A role to LiveKit grants mapping."""
        bridge = LiveKitBridge(
            api_key="test_key",
            api_secret="test_secret"
        )

        # Test admin role
        admin_grants = bridge._map_a2a_role_to_grants("admin", "test-room")
        assert admin_grants["roomAdmin"] is True
        assert admin_grants["canPublish"] is True
        assert admin_grants["recorder"] is True

        # Test viewer role
        viewer_grants = bridge._map_a2a_role_to_grants("viewer", "test-room")
        assert viewer_grants["roomAdmin"] is False
        assert viewer_grants["canPublish"] is False
        assert viewer_grants["canSubscribe"] is True

    def test_token_minting(self):
        """Test JWT token creation."""
        bridge = LiveKitBridge(
            api_key="test_key",
            api_secret="test_secret"
        )

        token = bridge.mint_access_token(
            identity="test_user",
            room_name="test_room",
            a2a_role="participant",
            ttl_minutes=30
        )

        # Basic validation - should be a non-empty string
        assert isinstance(token, str)
        assert len(token) > 0
        assert token.count('.') == 2  # JWT format


class TestMediaAgent:
    """Test MediaAgent functionality."""

    @pytest.mark.asyncio
    async def test_media_agent_without_bridge(self):
        """Test MediaAgent behavior without LiveKit bridge."""
        agent = MediaAgent()
        await agent.initialize()

        message = Message(parts=[Part(type="text", content="start video call")])
        response = await agent.process_message(message)

        assert len(response.parts) == 1
        assert "Media functionality is not available" in response.parts[0].text

    @pytest.mark.asyncio
    async def test_media_agent_with_mock_bridge(self):
        """Test MediaAgent with mocked LiveKit bridge."""
        agent = MediaAgent()

        # Mock the bridge
        mock_bridge = AsyncMock()
        mock_bridge.get_room_info.return_value = None  # Room doesn't exist
        mock_bridge.create_room.return_value = {
            "name": "test-room",
            "sid": "room-123",
            "max_participants": 50
        }
        mock_bridge.mint_access_token.return_value = "mock_token"
        mock_bridge.generate_join_url.return_value = "https://live.quantum-forge.net?room=test-room&token=mock_token"

        agent.livekit_bridge = mock_bridge

        message = Message(parts=[Part(type="text", content="create media session room test-room as test-user")])
        response = await agent.process_message(message)

        # Should have both text and data parts
        assert len(response.parts) == 2
        assert response.parts[0].kind == "text"
        assert "successfully" in response.parts[0].text.lower()
        assert response.parts[1].kind == "data"

        # Verify bridge was called
        mock_bridge.get_room_info.assert_called_once_with("test-room")
        mock_bridge.create_room.assert_called_once()
        mock_bridge.mint_access_token.assert_called_once()

    def test_message_parsing(self):
        """Test parsing of different media-related messages."""
        agent = MediaAgent()

        # Test video call parsing
        message = Message(parts=[Part(type="text", content="start video call room MyRoom")])
        action = agent._parse_media_action("start video call room MyRoom", message)
        assert action["type"] == "media-request"
        assert action["room_name"] == "MyRoom"

        # Test join room parsing
        message = Message(parts=[Part(type="text", content="join room MyRoom as moderator")])
        action = agent._parse_media_action("join room MyRoom as moderator", message)
        assert action["type"] == "media-join"
        assert action["room_name"] == "MyRoom"
        assert action["role"] == "moderator"

        # Test help parsing
        message = Message(parts=[Part(type="text", content="help with media")])
        action = agent._parse_media_action("help with media", message)
        assert action["type"] == "help"


@pytest.mark.asyncio
async def test_integration_with_mock_server():
    """Integration test with mocked LiveKit SDK."""
    from unittest.mock import MagicMock

    # Create mock room object
    mock_room = MagicMock()
    mock_room.name = "test-room"
    mock_room.sid = "room-123"
    mock_room.max_participants = 50
    mock_room.empty_timeout = 300
    mock_room.departure_timeout = 60
    mock_room.creation_time = 0
    mock_room.num_participants = 0
    mock_room.metadata = ""

    # Mock the LiveKit API
    with patch('livekit.api.LiveKitAPI') as mock_api_class:
        mock_api = MagicMock()
        mock_api_class.return_value = mock_api

        # Mock room service methods
        async def mock_create_room(request):
            return mock_room

        async def mock_list_rooms(request):
            return []

        mock_api.room.create_room = mock_create_room
        mock_api.room.list_rooms = mock_list_rooms

        bridge = LiveKitBridge(
            api_key="test_key",
            api_secret="test_secret",
            livekit_url="https://live.quantum-forge.net"
        )

        # Test room creation
        room_info = await bridge.create_room("test-room")
        assert room_info["name"] == "test-room"
        assert room_info["sid"] == "room-123"

        # Test room info retrieval (empty list)
        room_info = await bridge.get_room_info("nonexistent-room")
        assert room_info is None


if __name__ == "__main__":
    # Run a simple test to verify functionality
    import sys
    sys.path.append("/home/runner/work/A2A-Server-MCP/A2A-Server-MCP")

    # Test basic imports
    try:
        from a2a_server.livekit_bridge import LiveKitBridge
        from a2a_server.enhanced_agents import MediaAgent
        print("✅ Imports successful")
    except Exception as e:
        print(f"❌ Import failed: {e}")
        sys.exit(1)

    # Test basic functionality
    try:
        # Test bridge initialization
        bridge = LiveKitBridge(
            api_key="test_key",
            api_secret="test_secret"
        )
        print("✅ Bridge initialization successful")

        # Test token minting
        token = bridge.mint_access_token("test_user", "test_room")
        assert len(token) > 0
        print("✅ Token minting successful")

        # Test role mapping
        grants = bridge._map_a2a_role_to_grants("admin", "test_room")
        assert grants["roomAdmin"] is True
        print("✅ Role mapping successful")

        print("\n🎉 All basic tests passed!")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        sys.exit(1)
