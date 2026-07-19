# ruff: noqa: SLF001
"""Agent bridge fixtures with controlled persistence outcomes."""

from a2a_server.agent_bridge import AgentBridge


def bridge_with_save_result(saved: bool) -> AgentBridge:
    """Build a minimal bridge whose durable save has a fixed outcome."""
    bridge = AgentBridge.__new__(AgentBridge)
    bridge._tasks = {}
    bridge._codebase_tasks = {}

    async def save(_task: object) -> bool:
        return saved

    bridge._save_task = save
    return bridge
