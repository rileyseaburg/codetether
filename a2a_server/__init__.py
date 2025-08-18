"""
Agent2Agent (A2A) Protocol Server Implementation

This package provides a complete implementation of the A2A protocol specification,
enabling inter-agent communication and collaboration.
"""

__version__ = "0.1.0"
__author__ = "A2A Project Contributors"
__license__ = "Apache 2.0"

from .server import A2AServer
from .agent_card import AgentCard
from .message_broker import MessageBroker
from .task_manager import TaskManager

__all__ = [
    "A2AServer",
    "AgentCard", 
    "MessageBroker",
    "TaskManager",
]