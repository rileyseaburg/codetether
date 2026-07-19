"""Deterministic Temporal workflows for Forgejo coding-agent tasks."""

from __future__ import annotations

import asyncio

from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError

with workflow.unsafe.imports_passed_through():
    from .activities import (
        cancel_task,
        dispatch_fix,
        dispatch_review,
        dispatch_stage,
        finalize_workflow,
        publish_review,
    )
    from .models import (
        ForgejoAgentWorkflowInput,
        ForgejoAgentWorkflowResult,
        ForgejoControlSignal,
        ForgejoStageRequest,
        ForgejoStageResult,
        ForgejoTaskTerminalSignal,
    )

_ACTIVITY_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=1),
    maximum_attempts=5,
)
_TERMINAL_STATUSES = {'completed', 'failed', 'cancelled'}
_BLOCKING_VERDICTS = {'CHANGES_REQUESTED', 'BLOCKED'}


@workflow.defn(name='ForgejoAgentWorkflow')
class ForgejoAgentWorkflow:
    """Durably orchestrate one Forgejo task without sensitive history data."""

    def __init__(self) -> None:
        self._terminal: dict[str, ForgejoTaskTerminalSignal] = {}
        self._cancel_requested = False
        self._retry_requested = False
        self._active_task_id = ''
        self._completed_stages: list[str] = []
        self._review_verdict = ''

    @workflow.signal(name='task_terminal')
    async def task_terminal(self, signal: ForgejoTaskTerminalSignal) -> None:
        if signal.status in _TERMINAL_STATUSES:
            self._terminal[signal.task_id] = signal

    @workflow.signal(name='control')
    async def control(self, signal: ForgejoControlSignal) -> None:
        if signal.action == 'cancel':
            self._cancel_requested = True
        elif signal.action == 'retry':
            self._retry_requested = True
            self._cancel_requested = True

    @workflow.query(name='state')
    def state(self) -> dict[str, Any]:
        return {
            'active_task_id': self._active_task_id,
            'completed_stages': list(self._completed_stages),
            'review_verdict': self._review_verdict,
            'cancel_requested': self._cancel_requested,
            'retry_requested': self._retry_requested,
        }

    async def _activity(
        self, fn, arg, *, timeout: timedelta = timedelta(minutes=5)
    ):
        return await workflow.execute_activity(
            fn,
            arg,
            start_to_close_timeout=timeout,
            retry_policy=_ACTIVITY_RETRY,
        )

    async def _wait_terminal(
        self, stage: ForgejoStageResult
    ) -> ForgejoTaskTerminalSignal:
        self._active_task_id = stage.task_id
        try:
            await workflow.wait_condition(
                lambda: (
                    stage.task_id in self._terminal or self._cancel_requested
                ),
                timeout=timedelta(days=7),
            )
        except asyncio.TimeoutError:
            await self._activity(
                cancel_task, stage.task_id, timeout=timedelta(minutes=2)
            )
            return ForgejoTaskTerminalSignal(
                task_id=stage.task_id,
                stage=stage.stage,
                status='failed',
            )
        if self._cancel_requested:
            await self._activity(
                cancel_task, stage.task_id, timeout=timedelta(minutes=2)
            )
            return ForgejoTaskTerminalSignal(
                task_id=stage.task_id,
                stage=stage.stage,
                status='cancelled',
            )
        terminal = self._terminal.pop(stage.task_id)
        if terminal.status == 'completed':
            self._completed_stages.append(stage.stage)
        return terminal

    async def _finalize(
        self,
        workflow_input: ForgejoAgentWorkflowInput,
        status: str,
        *,
        error_type: str = '',
    ) -> ForgejoAgentWorkflowResult:
        await self._activity(
            finalize_workflow,
            {
                'repository': workflow_input.repository,
                'forgejo_task_id': workflow_input.forgejo_task_id,
                'issue_number': workflow_input.issue_number,
                'attempt': workflow_input.attempt,
                'status': status,
                'active_task_id': self._active_task_id,
            },
        )
        return ForgejoAgentWorkflowResult(
            forgejo_task_id=workflow_input.forgejo_task_id,
            attempt=workflow_input.attempt,
            status=status,
            active_task_id=self._active_task_id,
            completed_stages=list(self._completed_stages),
            review_verdict=self._review_verdict,
            error_type=error_type,
        )

    def _next_attempt(
        self, workflow_input: ForgejoAgentWorkflowInput
    ) -> ForgejoAgentWorkflowInput:
        return ForgejoAgentWorkflowInput(
            forgejo_task_id=workflow_input.forgejo_task_id,
            repository=workflow_input.repository,
            issue_number=workflow_input.issue_number,
            pull_request_number=workflow_input.pull_request_number,
            workspace_id=workflow_input.workspace_id,
            branch=workflow_input.branch,
            head_sha=workflow_input.head_sha,
            operation=workflow_input.operation,
            attempt=workflow_input.attempt + 1,
        )

    async def _finish_attempt(
        self,
        workflow_input: ForgejoAgentWorkflowInput,
        status: str,
        *,
        error_type: str,
    ) -> ForgejoAgentWorkflowResult:
        result = await self._finalize(
            workflow_input, status, error_type=error_type
        )
        if status not in {'failed', 'cancelled'}:
            return result
        if not self._retry_requested:
            try:
                await workflow.wait_condition(
                    lambda: self._retry_requested,
                    timeout=timedelta(days=7),
                )
            except asyncio.TimeoutError:
                return result
        workflow.continue_as_new(self._next_attempt(workflow_input))
        return result

    async def _stage(
        self,
        workflow_input: ForgejoAgentWorkflowInput,
        stage: str,
        *,
        parent_task_id: str = '',
        review_task_id: str = '',
        fix_attempt: int = 0,
    ) -> tuple[ForgejoStageResult, ForgejoTaskTerminalSignal]:
        request = ForgejoStageRequest(
            workflow=workflow_input,
            workflow_id=workflow.info().workflow_id,
            stage=stage,
            parent_task_id=parent_task_id,
            review_task_id=review_task_id,
            fix_attempt=fix_attempt,
        )
        if stage in {'prepare', 'code'}:
            result = await self._activity(dispatch_stage, request)
        elif stage == 'review':
            result = await self._activity(dispatch_review, request)
        elif stage == 'fix':
            result = await self._activity(dispatch_fix, request)
        else:
            raise ValueError(f'unsupported Forgejo stage: {stage}')
        return result, await self._wait_terminal(result)

    async def _run_attempt(
        self, workflow_input: ForgejoAgentWorkflowInput
    ) -> ForgejoAgentWorkflowResult:
        prepare, terminal = await self._stage(workflow_input, 'prepare')
        if terminal.status != 'completed':
            return await self._finish_attempt(
                workflow_input,
                terminal.status,
                error_type='prepare_failed',
            )

        code, terminal = await self._stage(
            workflow_input, 'code', parent_task_id=prepare.task_id
        )
        if terminal.status != 'completed':
            return await self._finish_attempt(
                workflow_input, terminal.status, error_type='code_failed'
            )

        parent_task_id = code.task_id
        for fix_attempt in range(0, 3):
            review, terminal = await self._stage(
                workflow_input,
                'review',
                parent_task_id=parent_task_id,
                fix_attempt=fix_attempt,
            )
            if terminal.status != 'completed':
                return await self._finish_attempt(
                    workflow_input,
                    terminal.status,
                    error_type='review_failed',
                )
            self._review_verdict = await self._activity(
                publish_review, review.task_id
            )
            if self._review_verdict == 'APPROVED':
                return await self._finalize(workflow_input, 'completed')
            if self._review_verdict not in _BLOCKING_VERDICTS:
                return await self._finish_attempt(
                    workflow_input,
                    'failed',
                    error_type='review_unresolved',
                )
            if fix_attempt >= 2:
                return await self._finish_attempt(
                    workflow_input,
                    'failed',
                    error_type='fix_attempts_exhausted',
                )
            fix, terminal = await self._stage(
                workflow_input,
                'fix',
                parent_task_id=parent_task_id,
                review_task_id=review.task_id,
                fix_attempt=fix_attempt + 1,
            )
            if terminal.status != 'completed':
                return await self._finish_attempt(
                    workflow_input,
                    terminal.status,
                    error_type='fix_failed',
                )
            parent_task_id = fix.task_id

        return await self._finish_attempt(
            workflow_input, 'failed', error_type='workflow_exhausted'
        )

    @workflow.run
    async def run(
        self, workflow_input: ForgejoAgentWorkflowInput
    ) -> ForgejoAgentWorkflowResult:
        try:
            return await self._run_attempt(workflow_input)
        except ActivityError as error:
            cause = error.cause
            error_type = (
                cause.type
                if isinstance(cause, ApplicationError) and cause.type
                else 'activity_failed'
            )
            return await self._finish_attempt(
                workflow_input,
                'failed',
                error_type=error_type,
            )
