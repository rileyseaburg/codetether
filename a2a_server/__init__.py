"""
Agent2Agent (A2A) Protocol Server Implementation

This package provides a complete implementation of the A2A protocol specification,
enabling inter-agent communication and collaboration.
"""

from importlib import import_module

__version__ = '0.1.0'
__author__ = 'A2A Project Contributors'
__license__ = 'Apache 2.0'


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


def __getattr__(name):
    if name == 'A2AServer':
        return import_module('.server', __name__).A2AServer
    if name == 'AgentCard':
        return import_module('.agent_card', __name__).AgentCard
    if name == 'MessageBroker':
        return import_module('.message_broker', __name__).MessageBroker
    if name == 'TaskManager':
        return import_module('.task_manager', __name__).TaskManager
    if name == 'A2AAgentCard':
        return import_module('.a2a_agent_card', __name__).A2AAgentCard
    if name == 'create_a2a_agent_card':
        return import_module('.a2a_agent_card', __name__).create_a2a_agent_card
    if name == 'a2a_agent_card_router':
        return import_module('.a2a_agent_card', __name__).a2a_agent_card_router
    raise AttributeError(name)
