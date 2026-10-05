"""Temporal client helpers for Forgejo workflow start and signals."""

from __future__ import annotations

import logging

from contextlib import suppress

from temporalio.client import WorkflowHandle
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

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
    # A retry after a lost response must not rerun terminal work.
    with suppress(WorkflowAlreadyStartedError):
        await client.start_workflow(
            ForgejoAgentWorkflow.run,
            workflow_input,
            id=workflow_id,
            task_queue=temporal_settings().task_queue,
            id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
            id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
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
    if signal.action == 'retry':
        from a2a_server import forgejo_inbox as inbox  # noqa: PLC0415

        pool = await inbox.pool()
        async with pool.acquire() as conn:
            await inbox.ensure_schema(conn)
            receipt = await conn.fetchrow(
                """
                SELECT context, api_base FROM forgejo_webhook_inbox
                WHERE native_task_id = $1
                ORDER BY received_at DESC LIMIT 1
            """,
                signal.forgejo_task_id,
            )
        if receipt:
            ctx = inbox.decode(receipt['context'])
            async with inbox.execution_ownership(
                ctx['repo'],
                ctx['number'],
                signal.forgejo_task_id,
                receipt['api_base'],
                attempt=2,
            ):
                await handle.signal(ForgejoAgentWorkflow.control, signal)
            return
        # Legacy tasks are also checked at stage creation, once their issue
        # identifiers are available. This closes the signal-to-activity race.
    await handle.signal(ForgejoAgentWorkflow.control, signal)
