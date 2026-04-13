"""Routing helpers for targeted worker task delivery."""

from typing import Optional


def is_targeted_clone_task(
    agent_type: Optional[str],
    target_agent_name: Optional[str] = None,
    target_worker_id: Optional[str] = None,
) -> bool:
    """Return True when a targeted clone task should bypass codebase ownership."""
    return agent_type == 'clone_repo' and bool(
        target_agent_name or target_worker_id
    )


def target_agent_mismatch(
    worker_agent_name: Optional[str], target_agent_name: Optional[str]
) -> bool:
    """Return True when a targeted task is being claimed by the wrong agent."""
    return bool(target_agent_name) and worker_agent_name != target_agent_name
