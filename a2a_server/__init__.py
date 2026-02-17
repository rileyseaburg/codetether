"""
Agent2Agent (A2A) Protocol Server Implementation

This package provides a complete implementation of the A2A protocol specification,
enabling inter-agent communication and collaboration.
"""

__version__ = '0.1.0'
__author__ = 'A2A Project Contributors'
__license__ = 'Apache 2.0'

from .server import A2AServer
from .agent_card import AgentCard
from .message_broker import MessageBroker
from .task_manager import TaskManager
from .a2a_agent_card import (
    A2AAgentCard,
    create_a2a_agent_card,
    a2a_agent_card_router,
)


# Lazy import for agent bridge to avoid dependency issues
def get_agent_bridge():
    """Get the agent bridge for managing codebases, tasks, and SSE workers."""
    from .agent_bridge import get_bridge

    return get_bridge()


__all__ = [
    'A2AServer',
    'AgentCard',
    'A2AAgentCard',
    'create_a2a_agent_card',
    'a2a_agent_card_router',
    'MessageBroker',
    'TaskManager',
    'get_agent_bridge',
]
