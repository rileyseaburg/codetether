"""
Backward-compatibility stub — all code has moved to agent_bridge.py

This module re-exports everything from agent_bridge so that existing
imports like ``from .opencode_bridge import OpenCodeBridge`` continue
to work without changes.

New code should import from ``a2a_server.agent_bridge`` instead.
"""

from .agent_bridge import *  # noqa: F401,F403
from .agent_bridge import (  # explicit re-exports for type-checkers
    AgentBridge,
    AgentStatus,
    AgentTaskStatus,
    AgentTask,
    AgentTriggerRequest,
    AgentTriggerResponse,
    RegisteredCodebase,
    OpenCodeBridge,
    get_bridge,
    get_agent_bridge,
    init_bridge,
    is_knative_enabled,
    resolve_model,
    MODEL_SELECTOR,
    MODEL_SELECTOR_KEYS,
    OPENCODE_HOST,
    OPENCODE_DEFAULT_PORT,
)
