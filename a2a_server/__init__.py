"""Agent2Agent (A2A) Protocol Server Implementation.

This package provides a complete implementation of the A2A protocol
specification, enabling inter-agent communication and collaboration.
"""

from importlib import import_module


__version__ = '0.1.0'
__author__ = 'A2A Project Contributors'
__license__ = 'Apache 2.0'


# Lazy import for agent bridge to avoid dependency issues
def get_agent_bridge():
    """Get the agent bridge for managing codebases, tasks, and SSE workers."""
    from a2a_server.agent_bridge import get_bridge  # noqa: PLC0415

    return get_bridge()


__all__ = [
    'A2AAgentCard',
    'A2AServer',
    'AgentCard',
    'MessageBroker',
    'TaskManager',
    'a2a_agent_card_router',
    'create_a2a_agent_card',
    'get_agent_bridge',
]


_LAZY_ATTRS = {
    'A2AServer': ('.server', 'A2AServer'),
    'AgentCard': ('.agent_card', 'AgentCard'),
    'MessageBroker': ('.message_broker', 'MessageBroker'),
    'TaskManager': ('.task_manager', 'TaskManager'),
    'A2AAgentCard': ('.a2a_agent_card', 'A2AAgentCard'),
    'create_a2a_agent_card': ('.a2a_agent_card', 'create_a2a_agent_card'),
    'a2a_agent_card_router': ('.a2a_agent_card', 'a2a_agent_card_router'),
}


def __getattr__(name: str) -> object:
    target = _LAZY_ATTRS.get(name)
    if target is not None:
        module_name, attr = target
        return getattr(import_module(module_name, __name__), attr)
    # Resolve any real submodule (e.g. spiffe_auth) on demand.
    try:
        return import_module('.' + name, __name__)
    except ModuleNotFoundError:
        raise AttributeError(name) from None
