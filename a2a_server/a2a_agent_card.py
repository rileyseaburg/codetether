"""
A2A Protocol Compliant Agent Card

Implements the official A2A specification AgentCard served at /.well-known/agent-card.json
for agent discovery and capability advertisement per the A2A protocol v0.3.
"""

import os
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter
from fastapi.responses import JSONResponse


# A2A Protocol v0.3 Compliant Models
# Based on specification/json/a2a.json


class AgentProvider(BaseModel):
    """Represents the service provider of an agent."""

    organization: str = Field(
        ..., description="The name of the agent provider's organization"
    )
    url: str = Field(
        ...,
        description="A URL for the agent provider's website or documentation",
    )


class AgentExtension(BaseModel):
    """A declaration of a protocol extension supported by an Agent."""

    uri: str = Field(
        ..., description='The unique URI identifying the extension'
    )
    description: Optional[str] = Field(
        default=None,
        description='A human-readable description of the extension',
    )
    required: Optional[bool] = Field(
        default=False,
        description='If true, the client must comply with the extension',
    )
    params: Optional[Dict[str, Any]] = Field(
        default=None, description='Extension-specific configuration parameters'
    )


class AgentCapabilities(BaseModel):
    """Defines optional capabilities supported by an agent."""

    streaming: Optional[bool] = Field(
        None,
        description='Indicates if the agent supports SSE for streaming responses',
    )
    pushNotifications: Optional[bool] = Field(
        None, description='Indicates if the agent supports push notifications'
    )
    stateTransitionHistory: Optional[bool] = Field(
        None,
        description='Indicates if the agent provides state transition history',
    )
    extensions: Optional[List[AgentExtension]] = Field(
        None, description='Protocol extensions supported by the agent'
    )


class AgentSkill(BaseModel):
    """Represents a distinct capability or function that an agent can perform."""

    id: str = Field(..., description='A unique identifier for the skill')
    name: str = Field(..., description='A human-readable name for the skill')
    description: str = Field(
        ..., description='A detailed description of the skill'
    )
    tags: List[str] = Field(
        default_factory=list, description='Keywords describing the skill'
    )
    examples: Optional[List[str]] = Field(
        default=None, description='Example prompts for the skill'
    )
    inputModes: Optional[List[str]] = Field(
        default=None,
        description='Supported input MIME types, overriding defaults',
    )
    outputModes: Optional[List[str]] = Field(
        default=None,
        description='Supported output MIME types, overriding defaults',
    )


class AgentInterface(BaseModel):
    """Declares a URL and transport protocol combination for interacting with the agent."""

    url: str = Field(
        ..., description='The URL where this interface is available'
    )
    transport: str = Field(
        ..., description='The transport protocol (JSONRPC, HTTP+JSON, GRPC)'
    )


class HTTPAuthSecurityScheme(BaseModel):
    """Defines a security scheme using HTTP authentication."""

    type: str = Field(default='http', description='Security scheme type')
    scheme: str = Field(..., description='HTTP auth scheme (e.g., Bearer)')
    bearerFormat: Optional[str] = Field(
        default=None, description='Format hint for bearer token (e.g., JWT)'
    )
    description: Optional[str] = Field(
        default=None, description='Description of the security scheme'
    )


class A2AAgentCard(BaseModel):
    """
    A2A Protocol v0.3 compliant AgentCard.

    The AgentCard is a self-describing manifest for an agent that provides
    essential metadata including identity, capabilities, skills, supported
    communication methods, and security requirements.
    """

    name: str = Field(..., description='A human-readable name for the agent')
    description: str = Field(
        ..., description="A description of the agent's purpose and capabilities"
    )
    url: str = Field(
        ...,
        description='The preferred endpoint URL for interacting with the agent',
    )
    version: str = Field(..., description="The agent's version number")
    protocolVersion: str = Field(
        '0.3', description='The A2A protocol version supported'
    )
    preferredTransport: str = Field(
        'JSONRPC',
        description='The transport protocol for the preferred endpoint',
    )
    additionalInterfaces: Optional[List[AgentInterface]] = Field(
        None, description='Additional supported interfaces'
    )
    capabilities: AgentCapabilities = Field(
        ..., description='Capabilities supported by the agent'
    )
    skills: List[AgentSkill] = Field(
        default_factory=list, description='Skills the agent can perform'
    )
    defaultInputModes: List[str] = Field(
        default_factory=list, description='Default supported input MIME types'
    )
    defaultOutputModes: List[str] = Field(
        default_factory=list, description='Default supported output MIME types'
    )
    provider: Optional[AgentProvider] = Field(
        None, description="Information about the agent's provider"
    )
    securitySchemes: Optional[Dict[str, HTTPAuthSecurityScheme]] = Field(
        None, description='Security schemes available for authorization'
    )
    security: Optional[List[Dict[str, List[str]]]] = Field(
        None, description='Security requirements for agent interactions'
    )
    documentationUrl: Optional[str] = Field(
        default=None, description="URL to the agent's documentation"
    )
    iconUrl: Optional[str] = Field(
        default=None, description='URL to an icon for the agent'
    )


def get_package_version() -> str:
    """Get the package version from setup.py or fallback."""
    try:
        # Try to import from the installed package
        import importlib.metadata

        return importlib.metadata.version('codetether')
    except Exception:
        # Fallback to hardcoded version matching setup.py
        return '1.1.0'


def create_a2a_agent_card(
    base_url: Optional[str] = None,
) -> A2AAgentCard:
    """
    Create an A2A protocol v0.3 compliant AgentCard for CodeTether.

    Args:
        base_url: The base URL where the agent is hosted. If not provided,
                  uses A2A_BASE_URL env var or defaults to http://localhost:9000

    Returns:
        A2AAgentCard: The compliant agent card
    """
    # Determine base URL
    if base_url is None:
        base_url = os.environ.get('A2A_BASE_URL', 'http://localhost:9000')

    # Remove trailing slash if present
    base_url = base_url.rstrip('/')

    return A2AAgentCard(
        name='CodeTether',
        description='Agent-to-Agent coordination and task execution platform. '
        'CodeTether enables multi-agent orchestration, task queue management, '
        'and seamless communication between AI agents using the A2A protocol.',
        url=base_url,
        version=get_package_version(),
        protocolVersion='0.3',
        preferredTransport='JSONRPC',
        additionalInterfaces=[
            AgentInterface(url=base_url, transport='JSONRPC'),
            AgentInterface(url=f'{base_url}/v1/a2a', transport='JSONRPC'),
            AgentInterface(url=f'{base_url}/api', transport='HTTP+JSON'),
        ],
        capabilities=AgentCapabilities(
            streaming=True,
            pushNotifications=True,
            stateTransitionHistory=True,
            extensions=[
                AgentExtension(
                    uri='https://codetether.io/extensions/mcp',
                    description='Model Context Protocol integration for tool synchronization',
                    required=False,
                ),
                AgentExtension(
                    uri='https://codetether.io/extensions/worker-sse',
                    description='Server-Sent Events for worker task distribution',
                    required=False,
                ),
            ],
        ),
        skills=[
            AgentSkill(
                id='task-management',
                name='Task Management',
                description='Create, query, update, and cancel tasks in the distributed task queue. '
                'Supports task prioritization, worker assignment, and status tracking.',
                tags=['tasks', 'queue', 'orchestration', 'workflow'],
                examples=[
                    'Create a new task for code review',
                    'Get the status of task abc-123',
                    'Cancel all pending tasks',
                    'List tasks assigned to worker-1',
                ],
            ),
            AgentSkill(
                id='agent-messaging',
                name='Agent Messaging',
                description='Send and receive messages between agents. Supports synchronous '
                'and asynchronous messaging with conversation threading.',
                tags=['messaging', 'communication', 'a2a', 'agents'],
                examples=[
                    'Send a message to the code-review agent',
                    'Get messages from conversation xyz',
                    'Broadcast a notification to all agents',
                ],
            ),
            AgentSkill(
                id='agent-discovery',
                name='Agent Discovery',
                description='Discover and register agents in the network. Query agent '
                'capabilities and maintain an up-to-date registry of available agents.',
                tags=['discovery', 'registry', 'agents', 'network'],
                examples=[
                    'List all available agents',
                    "Get details for agent 'code-assistant'",
                    'Register a new agent with the network',
                ],
            ),
            AgentSkill(
                id='worker-coordination',
                name='Worker Coordination',
                description='Coordinate worker agents for task execution. Supports SSE-based '
                'push notifications, task claiming, and progress reporting.',
                tags=['workers', 'coordination', 'sse', 'distributed'],
                examples=[
                    'Connect as a worker and wait for tasks',
                    'Claim the next available task',
                    'Report progress on task abc-123',
                ],
            ),
            AgentSkill(
                id='conversation-history',
                name='Conversation History',
                description='Retrieve and manage conversation history across agent interactions. '
                'Supports filtering by conversation ID, agent, and time range.',
                tags=['history', 'conversations', 'monitoring', 'audit'],
                examples=[
                    'Get the last 50 messages',
                    'Get conversation history for session xyz',
                    "Search messages containing 'error'",
                ],
            ),
        ],
        defaultInputModes=['text/plain', 'application/json'],
        defaultOutputModes=['text/plain', 'application/json'],
        provider=AgentProvider(
            organization='CodeTether',
            url='https://codetether.io',
        ),
        securitySchemes={
            'bearer': HTTPAuthSecurityScheme(
                type='http',
                scheme='Bearer',
                bearerFormat='JWT',
                description='JWT Bearer token authentication',
            )
        },
        security=[{'bearer': []}],
        documentationUrl='https://codetether.io/docs',
    )


# FastAPI Router for the /.well-known/agent-card.json endpoint
a2a_agent_card_router = APIRouter(tags=['A2A Discovery'])


@a2a_agent_card_router.get(
    '/.well-known/agent-card.json',
    response_class=JSONResponse,
    summary='A2A Agent Card',
    description='Returns the A2A protocol v0.3 compliant agent card for discovery',
    responses={
        200: {
            'description': 'A2A AgentCard for agent discovery',
            'content': {
                'application/json': {
                    'example': {
                        'name': 'CodeTether',
                        'description': 'Agent-to-Agent coordination platform',
                        'url': 'https://api.codetether.io',
                        'version': '1.1.0',
                        'protocolVersion': '0.3',
                        'capabilities': {
                            'streaming': True,
                            'pushNotifications': True,
                            'stateTransitionHistory': True,
                        },
                    }
                }
            },
        }
    },
)
async def get_a2a_agent_card() -> JSONResponse:
    """
    Serve the A2A protocol compliant agent card.

    This endpoint follows the A2A specification for agent discovery,
    allowing other agents and clients to discover this agent's
    capabilities, skills, and communication protocols.
    """
    agent_card = create_a2a_agent_card()
    return JSONResponse(
        content=agent_card.model_dump(exclude_none=True),
        headers={
            'Content-Type': 'application/json',
            'Cache-Control': 'public, max-age=3600',
        },
    )
