"""Routing helpers for targeted worker task delivery."""

from typing import Optional


def is_clone_task(
    agent_type: Optional[str],
) -> bool:
    """Return True when a task is a clone/refresh operation.

    Clone tasks create workspaces on workers, so they must bypass codebase
    ownership checks — the workspace doesn't exist yet anywhere.
    """
    return agent_type == 'clone_repo'


def is_targeted_clone_task(
    agent_type: Optional[str],
    target_agent_name: Optional[str] = None,
    target_worker_id: Optional[str] = None,
) -> bool:
    """Return True when ANY clone task (targeted or not) should bypass codebase ownership.

    Clone tasks are the bootstrap step: they create the workspace directory
    and clone the repo.  At this point no worker owns the codebase yet, so
    restricting by codebase ownership would deadlock the pipeline.
    """
    return is_clone_task(agent_type)


def target_agent_mismatch(
    worker_agent_name: Optional[str], target_agent_name: Optional[str]
) -> bool:
    """Return True when a targeted task is being claimed by the wrong agent."""
    return bool(target_agent_name) and worker_agent_name != target_agent_name
