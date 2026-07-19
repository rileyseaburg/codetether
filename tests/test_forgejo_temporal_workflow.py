from __future__ import annotations

import asyncio

from dataclasses import asdict
from datetime import timedelta

import pytest

from temporalio import activity
from temporalio.client import WorkflowHistoryEventFilterType
from temporalio.exceptions import ApplicationError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from a2a_server.temporal.models import (
    ForgejoAgentWorkflowInput,
    ForgejoControlSignal,
    ForgejoStageRequest,
    ForgejoStageResult,
    ForgejoTaskTerminalSignal,
)
from a2a_server.temporal.workflows import ForgejoAgentWorkflow


class FakeActivities:
    def __init__(self, verdicts: list[str] | None = None, fail_stage: str = ''):
        self.dispatched: list[ForgejoStageRequest] = []
        self.results: list[ForgejoStageResult] = []
        self.cancelled: list[str] = []
        self.finalized: list[dict] = []
        self.verdicts = list(verdicts or ['APPROVED'])
        self.fail_stage = fail_stage
        self.counter = 0

    def _result(self, request: ForgejoStageRequest) -> ForgejoStageResult:
        self.counter += 1
        self.dispatched.append(request)
        result = ForgejoStageResult(
            task_id=f'{request.stage}-{self.counter}',
            stage=request.stage,
            pull_request_number=request.workflow.pull_request_number or 7,
            branch='feature',
            head_sha='abc123',
        )
        self.results.append(result)
        return result

    @activity.defn(name='forgejo_dispatch_stage')
    async def dispatch_stage(
        self, request: ForgejoStageRequest
    ) -> ForgejoStageResult:
        if request.stage == self.fail_stage:
            raise ApplicationError(
                'forgejo_dispatch_stage_failed',
                type='forgejo_dispatch_stage_failed',
            )
        return self._result(request)

    @activity.defn(name='forgejo_dispatch_review')
    async def dispatch_review(
        self, request: ForgejoStageRequest
    ) -> ForgejoStageResult:
        return self._result(request)

    @activity.defn(name='forgejo_dispatch_fix')
    async def dispatch_fix(
        self, request: ForgejoStageRequest
    ) -> ForgejoStageResult:
        return self._result(request)

    @activity.defn(name='forgejo_publish_review')
    async def publish_review(self, review_task_id: str) -> str:
        assert review_task_id.startswith('review-')
        return self.verdicts.pop(0)

    @activity.defn(name='forgejo_cancel_task')
    async def cancel_task(self, task_id: str) -> bool:
        self.cancelled.append(task_id)
        return True

    @activity.defn(name='forgejo_finalize_workflow')
    async def finalize_workflow(self, payload: dict) -> None:
        self.finalized.append(payload)

    @property
    def registered(self):
        return [
            self.dispatch_stage,
            self.dispatch_review,
            self.publish_review,
            self.dispatch_fix,
            self.cancel_task,
            self.finalize_workflow,
        ]


INPUT = ForgejoAgentWorkflowInput(
    forgejo_task_id=42,
    repository='acme/widgets',
    issue_number=7,
    pull_request_number=7,
    workspace_id='workspace-1',
    branch='feature',
    head_sha='abc123',
    operation='fix',
)


async def wait_for_stage(handle, stage: str) -> str:
    for _ in range(100):
        state = await handle.query(ForgejoAgentWorkflow.state)
        active = str(state['active_task_id'])
        if active.startswith(f'{stage}-'):
            return active
        await asyncio.sleep(0.01)
    raise AssertionError(f'workflow never reached {stage}')


async def wait_for_dispatched(
    activities: FakeActivities, stage: str, occurrence: int
) -> str:
    for _ in range(200):
        results = [
            result for result in activities.results if result.stage == stage
        ]
        if len(results) >= occurrence:
            return results[occurrence - 1].task_id
        await asyncio.sleep(0.01)
    raise AssertionError(
        f'workflow never dispatched {stage} occurrence {occurrence}'
    )


async def complete(handle, task_id: str, stage: str, status='completed'):
    await handle.signal(
        ForgejoAgentWorkflow.task_terminal,
        ForgejoTaskTerminalSignal(
            task_id=task_id,
            stage=stage,
            status=status,
            head_sha='abc123',
            pull_request_number=7,
        ),
    )


@pytest.mark.asyncio
async def test_temporal_forgejo_workflow_approval_and_safe_history():
    activities = FakeActivities(['APPROVED'])
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue='forgejo-test',
            workflows=[ForgejoAgentWorkflow],
            activities=activities.registered,
        ):
            handle = await env.client.start_workflow(
                ForgejoAgentWorkflow.run,
                INPUT,
                id='forgejo-agent-task-42-success',
                task_queue='forgejo-test',
            )
            prepare = await wait_for_stage(handle, 'prepare')
            await complete(handle, prepare, 'prepare')
            code = await wait_for_stage(handle, 'code')
            await complete(handle, code, 'code')
            review = await wait_for_stage(handle, 'review')
            await complete(handle, review, 'review')
            result = await handle.result()

            assert result.status == 'completed'
            assert result.completed_stages == ['prepare', 'code', 'review']
            assert result.review_verdict == 'APPROVED'
            assert activities.finalized[-1]['status'] == 'completed'

            history = await handle.fetch_history(
                event_filter_type=WorkflowHistoryEventFilterType.ALL_EVENT
            )
            encoded = str(history).lower()
            for forbidden in (
                'must-not-leak',
                'authorization:',
                'private key',
                'tool_calls',
                'clone_url',
                'prompt',
                'transcript',
            ):
                assert forbidden not in encoded
            assert 'acme/widgets' in encoded


@pytest.mark.asyncio
async def test_temporal_blocking_review_runs_fix_and_rereview():
    activities = FakeActivities(['CHANGES_REQUESTED', 'APPROVED'])
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue='forgejo-test-fix',
            workflows=[ForgejoAgentWorkflow],
            activities=activities.registered,
        ):
            handle = await env.client.start_workflow(
                ForgejoAgentWorkflow.run,
                INPUT,
                id='forgejo-agent-task-42-fix',
                task_queue='forgejo-test-fix',
            )
            for stage in ('prepare', 'code', 'review', 'fix', 'review'):
                task_id = await wait_for_stage(handle, stage)
                await complete(handle, task_id, stage)
            result = await handle.result()

    assert result.status == 'completed'
    assert [request.stage for request in activities.dispatched] == [
        'prepare',
        'code',
        'review',
        'fix',
        'review',
    ]
    fix_request = activities.dispatched[3]
    assert fix_request.fix_attempt == 1
    assert fix_request.review_task_id.startswith('review-')


@pytest.mark.asyncio
async def test_temporal_cancel_propagates_to_active_task():
    activities = FakeActivities()
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue='forgejo-test-cancel',
            workflows=[ForgejoAgentWorkflow],
            activities=activities.registered,
        ):
            handle = await env.client.start_workflow(
                ForgejoAgentWorkflow.run,
                INPUT,
                id='forgejo-agent-task-42-cancel',
                task_queue='forgejo-test-cancel',
            )
            prepare = await wait_for_stage(handle, 'prepare')
            await handle.signal(
                ForgejoAgentWorkflow.control,
                ForgejoControlSignal(action='cancel', forgejo_task_id=42),
            )
            for _ in range(100):
                if prepare in activities.cancelled:
                    break
                await asyncio.sleep(0.01)
            assert prepare in activities.cancelled
            state = await handle.query(ForgejoAgentWorkflow.state)
            assert state['cancel_requested'] is True
            await env.sleep(timedelta(days=8))
            result = await handle.result()

    assert result.status == 'cancelled'
    assert activities.finalized[-1]['status'] == 'cancelled'


@pytest.mark.asyncio
async def test_temporal_retry_continues_as_new_attempt():
    activities = FakeActivities(['APPROVED'])
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue='forgejo-test-retry',
            workflows=[ForgejoAgentWorkflow],
            activities=activities.registered,
        ):
            handle = await env.client.start_workflow(
                ForgejoAgentWorkflow.run,
                INPUT,
                id='forgejo-agent-task-42-retry',
                task_queue='forgejo-test-retry',
            )
            first_prepare = await wait_for_stage(handle, 'prepare')
            await complete(handle, first_prepare, 'prepare', status='failed')
            for _ in range(100):
                if activities.finalized:
                    break
                await asyncio.sleep(0.01)
            assert activities.finalized[-1]['status'] == 'failed'
            await handle.signal(
                ForgejoAgentWorkflow.control,
                ForgejoControlSignal(action='retry', forgejo_task_id=42),
            )
            second_prepare = await wait_for_dispatched(activities, 'prepare', 2)
            assert second_prepare != first_prepare
            assert activities.dispatched[-1].workflow.attempt == 2
            await complete(handle, second_prepare, 'prepare')
            code = await wait_for_dispatched(activities, 'code', 1)
            await complete(handle, code, 'code')
            review = await wait_for_dispatched(activities, 'review', 1)
            await complete(handle, review, 'review')
            result = await handle.result()

    assert result.status == 'completed'
    assert result.attempt == 2
    assert asdict(activities.dispatched[-1].workflow)['forgejo_task_id'] == 42


@pytest.mark.asyncio
async def test_temporal_activity_exhaustion_projects_failed_attempt():
    activities = FakeActivities(fail_stage='prepare')
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue='forgejo-test-activity-failure',
            workflows=[ForgejoAgentWorkflow],
            activities=activities.registered,
        ):
            handle = await env.client.start_workflow(
                ForgejoAgentWorkflow.run,
                INPUT,
                id='forgejo-agent-task-42-activity-failure',
                task_queue='forgejo-test-activity-failure',
            )
            result = await handle.result()

    assert result.status == 'failed'
    assert result.error_type == 'forgejo_dispatch_stage_failed'
    assert activities.finalized[-1]['status'] == 'failed'
