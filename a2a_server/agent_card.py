"""
Agent Card implementation for A2A protocol.

Provides utilities for creating, managing, and serving agent cards
for agent discovery and capability advertisement.
"""

import json
from typing import List, Optional, Dict, Any
from pathlib import Path

from .models import (
    AgentCard as AgentCardModel,
    AgentProvider,
    AgentCapabilities,
    AgentSkill,
    AuthenticationScheme,
    AgentExtension,
    AgentInterface,
    AdditionalInterfaces,
    LiveKitInterface
)


class AgentCard:
    """Helper class for creating and managing A2A Agent Cards."""

    def __init__(
        self,
        name: str,
        description: str,
        url: str,
        provider: AgentProvider,
        capabilities: Optional[AgentCapabilities] = None,
        authentication: Optional[List[AuthenticationScheme]] = None,
        skills: Optional[List[AgentSkill]] = None,
        additional_interfaces: Optional[List[AgentInterface]] = None,
        version: str = "1.0"
    ):
        self.card = AgentCardModel(
            name=name,
            description=description,
            url=url,
            provider=provider,
            capabilities=capabilities or AgentCapabilities(),
            authentication=authentication or [],
            skills=skills or [],
            additional_interfaces=additional_interfaces or [],
            version=version
        )

    def add_skill(
        self,
        skill_id: str,
        name: str,
        description: str,
        input_modes: Optional[List[str]] = None,
        output_modes: Optional[List[str]] = None,
        examples: Optional[List[str]] = None
    ) -> 'AgentCard':
        """Add a skill to the agent card."""
        skill = AgentSkill(
            id=skill_id,
            name=name,
            description=description,
            input_modes=input_modes or ["text"],
            output_modes=output_modes or ["text"],
            examples=examples or []
        )
        self.card.skills.append(skill)
        return self

    def add_authentication(
        self,
        scheme: str,
        description: Optional[str] = None
    ) -> 'AgentCard':
        """Add an authentication scheme to the agent card."""
        auth = AuthenticationScheme(
            scheme=scheme,
            description=description
        )
        self.card.authentication.append(auth)
        return self

    def enable_streaming(self) -> 'AgentCard':
        """Enable streaming capability."""
        if not self.card.capabilities:
            self.card.capabilities = AgentCapabilities()
        self.card.capabilities.streaming = True
        return self

    def enable_push_notifications(self) -> 'AgentCard':
        """Enable push notifications capability."""
        if not self.card.capabilities:
            self.card.capabilities = AgentCapabilities()
        self.card.capabilities.push_notifications = True
        return self

    def enable_state_history(self) -> 'AgentCard':
        """Enable state transition history capability."""
        if not self.card.capabilities:
            self.card.capabilities = AgentCapabilities()
        self.card.capabilities.state_transition_history = True
        return self

    def enable_media(self) -> 'AgentCard':
        """Enable media capability."""
        if not self.card.capabilities:
            self.card.capabilities = AgentCapabilities()
        self.card.capabilities.media = True
        return self

    def add_livekit_interface(
        self,
        token_endpoint: str,
        join_url_template: Optional[str] = None,
        server_managed: bool = True
    ) -> 'AgentCard':
        """Add LiveKit interface configuration.

        Args:
            token_endpoint: Endpoint for obtaining LiveKit access tokens
            join_url_template: Template for generating join URLs
            server_managed: Whether the server manages LiveKit resources
        """
        self.card.additional_interfaces.append(
            AgentInterface(
                transport='livekit',
                url=token_endpoint,
                content_types=['audio/pcm', 'video/h264'],
            )
        )

        # Also enable media capability
        self.enable_media()

        return self

    def add_mcp_interface(
        self,
        endpoint: str,
        protocol: str = "http",
        description: Optional[str] = None
    ) -> 'AgentCard':
        """Add MCP (Model Context Protocol) interface for agent synchronization.

        Args:
            endpoint: HTTP endpoint for MCP JSON-RPC (e.g., http://localhost:9000/mcp/v1/rpc)
            protocol: Protocol type (http, stdio, sse)
            description: Optional description of available MCP tools
        """
        self.card.additional_interfaces.append(
            AgentInterface(
                transport=f'mcp-{protocol}',
                url=endpoint,
                content_types=['application/json'],
            )
        )

        return self

    def add_extension(
        self,
        uri: str,
        description: Optional[str] = None,
        required: bool = False
    ) -> 'AgentCard':
        """Add a protocol extension to the agent card."""
        extension = AgentExtension(
            uri=uri,
            description=description,
            required=required
        )
        self.card.capabilities.extensions.append(extension)
        return self

    def to_dict(self) -> Dict[str, Any]:
        """Convert the agent card to a dictionary."""
        return self.card.model_dump(exclude_none=True)

    def to_json(self, indent: Optional[int] = 2) -> str:
        """Convert the agent card to JSON."""
        return self.card.model_dump_json(exclude_none=True, indent=indent)

    def save_to_file(self, file_path: str) -> None:
        """Save the agent card to a JSON file."""
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, 'w', encoding='utf-8') as f:
            f.write(self.to_json())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentCard':
        """Create an AgentCard from a dictionary."""
        card_model = AgentCardModel.model_validate(data)
        instance = cls.__new__(cls)
        instance.card = card_model
        return instance

    @classmethod
    def from_json(cls, json_str: str) -> 'AgentCard':
        """Create an AgentCard from a JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)

    @classmethod
    def from_file(cls, file_path: str) -> 'AgentCard':
        """Load an AgentCard from a JSON file."""
        with open(file_path, 'r', encoding='utf-8') as f:
            return cls.from_json(f.read())


class AgentCardBuilder:
    """Fluent builder for creating Agent Cards."""

    def __init__(self):
        self._name: Optional[str] = None
        self._description: Optional[str] = None
        self._url: Optional[str] = None
        self._provider: Optional[AgentProvider] = None
        self._capabilities: Optional[AgentCapabilities] = None
        self._authentication: List[AuthenticationScheme] = []
        self._skills: List[AgentSkill] = []
        self._additional_interfaces: List[AgentInterface] = []
        self._version: str = "1.0"

    def name(self, name: str) -> 'AgentCardBuilder':
        """Set the agent name."""
        self._name = name
        return self

    def description(self, description: str) -> 'AgentCardBuilder':
        """Set the agent description."""
        self._description = description
        return self

    def url(self, url: str) -> 'AgentCardBuilder':
        """Set the agent URL."""
        self._url = url
        return self

    def provider(
        self,
        organization: str,
        url: str
    ) -> 'AgentCardBuilder':
        """Set the agent provider information."""
        self._provider = AgentProvider(
            organization=organization,
            url=url
        )
        return self

    def with_streaming(self) -> 'AgentCardBuilder':
        """Enable streaming capability."""
        if not self._capabilities:
            self._capabilities = AgentCapabilities()
        self._capabilities.streaming = True
        return self

    def with_push_notifications(self) -> 'AgentCardBuilder':
        """Enable push notifications capability."""
        if not self._capabilities:
            self._capabilities = AgentCapabilities()
        self._capabilities.push_notifications = True
        return self

    def with_state_history(self) -> 'AgentCardBuilder':
        """Enable state transition history capability."""
        if not self._capabilities:
            self._capabilities = AgentCapabilities()
        self._capabilities.state_transition_history = True
        return self

    def with_media(self) -> 'AgentCardBuilder':
        """Enable media capability."""
        if not self._capabilities:
            self._capabilities = AgentCapabilities()
        self._capabilities.media = True
        return self

    def with_livekit_interface(
        self,
        token_endpoint: str,
        join_url_template: Optional[str] = None,
        server_managed: bool = True
    ) -> 'AgentCardBuilder':
        """Add LiveKit interface configuration."""
        self._additional_interfaces.append(
            AgentInterface(
                transport='livekit',
                url=token_endpoint,
                content_types=['audio/pcm', 'video/h264'],
            )
        )

        # Also enable media capability
        self.with_media()

        return self

    def with_extension(
        self,
        uri: str,
        description: Optional[str] = None,
        required: bool = False
    ) -> 'AgentCardBuilder':
        """Add a protocol extension."""
        if not self._capabilities:
            self._capabilities = AgentCapabilities()

        extension = AgentExtension(
            uri=uri,
            description=description,
            required=required
        )
        self._capabilities.extensions.append(extension)
        return self

    def with_authentication(
        self,
        scheme: str,
        description: Optional[str] = None
    ) -> 'AgentCardBuilder':
        """Add an authentication scheme."""
        auth = AuthenticationScheme(
            scheme=scheme,
            description=description
        )
        self._authentication.append(auth)
        return self

    def with_skill(
        self,
        skill_id: str,
        name: str,
        description: str,
        input_modes: Optional[List[str]] = None,
        output_modes: Optional[List[str]] = None,
        examples: Optional[List[str]] = None
    ) -> 'AgentCardBuilder':
        """Add a skill."""
        skill = AgentSkill(
            id=skill_id,
            name=name,
            description=description,
            input_modes=input_modes or ["text"],
            output_modes=output_modes or ["text"],
            examples=examples or []
        )
        self._skills.append(skill)
        return self

    def version(self, version: str) -> 'AgentCardBuilder':
        """Set the agent card version."""
        self._version = version
        return self

    def build(self) -> AgentCard:
        """Build the agent card."""
        if not all([self._name, self._description, self._url, self._provider]):
            raise ValueError("Name, description, URL, and provider are required")

        return AgentCard(
            name=self._name,
            description=self._description,
            url=self._url,
            provider=self._provider,
            capabilities=self._capabilities,
            authentication=self._authentication,
            skills=self._skills,
            additional_interfaces=self._additional_interfaces,
            version=self._version
        )


# Convenience function for creating agent cards
def create_agent_card(
    name: str,
    description: str,
    url: str,
    organization: str,
    organization_url: str
) -> AgentCardBuilder:
    """Create a new agent card builder with basic information."""
    return (AgentCardBuilder()
            .name(name)
            .description(description)
            .url(url)
            .provider(organization, organization_url))
