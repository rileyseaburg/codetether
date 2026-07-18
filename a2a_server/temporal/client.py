"""Temporal client helpers for Forgejo workflow start and signals."""

from __future__ import annotations

import logging

from temporalio.client import WorkflowHandle
from temporalio.common import WorkflowIDConflictPolicy

from .config import get_temporal_client, temporal_settings
from .models import (
    ForgejoAgentWorkflowInput,
    ForgejoControlSignal,
    ForgejoTaskTerminalSignal,
)
from .workflows import ForgejoAgentWorkflow

logger = logging.getLogger(__name__)


def forgejo_workflow_id(forgejo_task_id: int) -> str:
    """Return the stable workflow ID for one Forgejo-owned task."""
    return f'forgejo-agent-task-{forgejo_task_id}'


async def start_forgejo_workflow(
    workflow_input: ForgejoAgentWorkflowInput,
) -> str:
    """Start or attach to the idempotent workflow for a Forgejo task."""
    client = await get_temporal_client()
    workflow_id = forgejo_workflow_id(workflow_input.forgejo_task_id)
    await client.start_workflow(
        ForgejoAgentWorkflow.run,
        workflow_input,
        id=workflow_id,
        task_queue=temporal_settings().task_queue,
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )
    return workflow_id


async def workflow_handle(forgejo_task_id: int) -> WorkflowHandle:
    client = await get_temporal_client()
    return client.get_workflow_handle(forgejo_workflow_id(forgejo_task_id))


async def signal_task_terminal(
    forgejo_task_id: int,
    signal: ForgejoTaskTerminalSignal,
) -> None:
    """Signal one terminal CodeTether task projection into its workflow."""
    handle = await workflow_handle(forgejo_task_id)
    await handle.signal(ForgejoAgentWorkflow.task_terminal, signal)


async def signal_control(
    signal: ForgejoControlSignal,
) -> None:
    """Signal a signed native Forgejo cancel/retry request."""
    handle = await workflow_handle(signal.forgejo_task_id)
    await handle.signal(ForgejoAgentWorkflow.control, signal)
