"""Native issue workflows recover authoritative BLOCKED feedback instead of stopping."""

import pytest

from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker
from test_forgejo_temporal_workflow import (
    INPUT,
    FakeActivities,
    complete,
    wait_for_dispatched,
    wait_for_stage,
)

from a2a_server.temporal.models import ForgejoTaskTerminalSignal
from a2a_server.temporal.workflows import ForgejoAgentWorkflow


@pytest.mark.asyncio
async def test_blocked_owner_repairs_then_reenters_review_until_approved():
    fake = FakeActivities(['BLOCKED', 'APPROVED'])
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue='recovery-loop',
            workflows=[ForgejoAgentWorkflow],
            activities=fake.registered,
        ):
            handle = await env.client.start_workflow(
                ForgejoAgentWorkflow.run,
                INPUT,
                id='native-feedback-recovery',
                task_queue='recovery-loop',
            )
            for stage in ('prepare', 'code'):
                task_id = await wait_for_stage(handle, stage)
                await complete(handle, task_id, stage)
            review = await wait_for_stage(handle, 'review')
            await handle.signal(
                ForgejoAgentWorkflow.task_terminal,
                ForgejoTaskTerminalSignal(
                    task_id=review,
                    stage='review',
                    status='failed',
                    verdict='BLOCKED',
                    review_owner=True,
                ),
            )
            fix = await wait_for_stage(handle, 'fix')
            await complete(handle, fix, 'fix')
            second = await wait_for_dispatched(fake, 'review', 2)
            await handle.signal(
                ForgejoAgentWorkflow.task_terminal,
                ForgejoTaskTerminalSignal(
                    task_id=second,
                    stage='review',
                    status='completed',
                    verdict='APPROVED',
                    review_owner=True,
                ),
            )
            result = await handle.result()
    assert result.status == 'completed'
    assert result.review_verdict == 'APPROVED'
    assert [r.stage for r in fake.dispatched].count('fix') == 1
    assert [r.stage for r in fake.dispatched].count('review') == 2
