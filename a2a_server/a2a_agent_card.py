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

from .models import (
    AgentCapabilities,
    AgentCard as AgentCardModel,
    AgentExtension,
    AgentInterface,
    AgentProvider,
    AgentSkill,
    HTTPAuthSecurityScheme,
    SecurityScheme,
)


class A2AAgentCard(AgentCardModel):
    """
    A2A Protocol v0.3 compliant AgentCard.

    Extends the canonical AgentCard from models.py with legacy field aliases
    for backwards compatibility with existing serialization consumers.
    """

    pass


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
        protocol_version='0.3',
        preferred_transport='JSONRPC',
        additional_interfaces=[
            AgentInterface(url=base_url, transport='JSONRPC'),
            AgentInterface(url=f'{base_url}/v1/a2a', transport='JSONRPC'),
            AgentInterface(url=f'{base_url}/api', transport='HTTP+JSON'),
        ],
        capabilities=AgentCapabilities(
            streaming=True,
            push_notifications=True,
            state_transition_history=True,
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
            AgentSkill(
                id='proactive-monitoring',
                name='Proactive Monitoring',
                description='Event-driven rule engine that triggers autonomous agent actions '
                'based on events, cron schedules, or health-check thresholds. '
                'Rules are cooldown-protected and all triggers are audit-logged.',
                tags=['proactive', 'monitoring', 'rules', 'events', 'health-checks', 'autonomous'],
                examples=[
                    'Create a rule to deploy when tests pass on main',
                    'Set up a health check that pings /healthz every 60 seconds',
                    'List all rules that triggered today',
                ],
            ),
            AgentSkill(
                id='persona-swarms',
                name='Persona Swarms',
                description='Route tasks to specialized agent personas (monitor, deployer, reviewer) '
                'with scoped permissions. Each persona has a distinct system prompt, '
                'model tier, and allowed tools/paths/namespaces.',
                tags=['personas', 'swarms', 'specialization', 'permissions', 'routing'],
                examples=[
                    'Assign the monitor persona to watch health endpoints',
                    'Use the deployer persona for CI/CD tasks',
                    'List available persona profiles',
                ],
            ),
            AgentSkill(
                id='perpetual-cognition',
                name='Perpetual Cognition Loops',
                description='Persistent thought loops that survive server restarts. '
                'An agent persona iterates on a codebase with state carried between '
                'iterations, subject to daily cost ceilings and iteration limits. '
                'Model tier auto-downgrades at 80% budget to stretch spend.',
                tags=['perpetual', 'cognition', 'loops', 'autonomous', 'continuous', 'cost-control'],
                examples=[
                    'Start a monitoring loop on the production codebase',
                    'Pause the review loop until tomorrow',
                    'Show iteration history for loop abc-123',
                ],
            ),
            AgentSkill(
                id='autonomous-audit',
                name='Autonomous Decision Audit',
                description='Every autonomous decision — rule triggers, loop iterations, '
                'budget gates, model downgrades — is logged in a queryable audit trail. '
                'Provides full transparency into what agents did and why.',
                tags=['audit', 'decisions', 'transparency', 'compliance', 'logging'],
                examples=[
                    'List all autonomous decisions from the last hour',
                    'Show decisions made by the rule engine today',
                    'Filter audit trail by outcome=failed',
                ],
            ),
        ],
        default_input_modes=['text/plain', 'application/json'],
        default_output_modes=['text/plain', 'application/json'],
        provider=AgentProvider(
            organization='CodeTether',
            url='https://codetether.io',
        ),
        securitySchemes={
            'bearer': HTTPAuthSecurityScheme(
                type='http',
                scheme='Bearer',
                bearer_format='JWT',
                description='JWT Bearer token authentication',
            )
        },
        security=[{'bearer': []}],
        documentation_url='https://codetether.io/docs',
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
