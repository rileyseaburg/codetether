"""One durable, bounded review execution per PR head; no coding remediation."""

import asyncio

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError


with workflow.unsafe.imports_passed_through():
    from . import activities


@workflow.defn(name='ForgejoHeadReviewWorkflow')
class HeadReviewWorkflow:
    def __init__(self):
        self.cancelled = False
        self.retry_epoch = 0
        self.chunks = []

    @workflow.signal
    async def cancel(self):
        self.cancelled = True

    @workflow.signal
    async def retry(self, epoch: int):
        self.retry_epoch = max(self.retry_epoch, epoch)

    @workflow.query
    def state(self):
        return {'cancelled': self.cancelled, 'chunk_tasks': list(self.chunks)}

    async def call(self, fn, arg):
        return await workflow.execute_activity(
            fn,
            arg,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(
                maximum_attempts=5, initial_interval=timedelta(seconds=2)
            ),
        )

    @workflow.run
    async def run(self, arg):
        result = await self.review_once(arg)
        try:
            await workflow.wait_condition(
                lambda: self.retry_epoch > arg.get('attempt', 1),
                timeout=timedelta(days=7),
            )
        except asyncio.TimeoutError:
            return result
        workflow.continue_as_new({**arg, 'attempt': arg.get('attempt', 1) + 1})

    async def review_once(self, arg):
        try:
            count = await self.call(activities.prepare, arg)
            drain_deadline = workflow.now() + timedelta(minutes=30)
            while not count and not self.cancelled:
                if workflow.now() >= drain_deadline:
                    return await self.call(
                        activities.complete,
                        {
                            **arg,
                            'blocked': True,
                            'reason': 'review_legacy_drain_timeout',
                        },
                    )
                try:
                    await workflow.wait_condition(
                        lambda: self.cancelled, timeout=timedelta(seconds=15)
                    )
                except asyncio.TimeoutError:
                    pass
                count = await self.call(activities.prepare, arg)
            deadline = workflow.now() + timedelta(hours=3)
            for start in range(1, count + 1, 2):
                batch = []
                for index in range(start, min(start + 2, count + 1)):
                    if self.cancelled:
                        break
                    task_id = await self.call(
                        activities.dispatch, {**arg, 'index': index}
                    )
                    batch.append(task_id)
                    self.chunks.append(task_id)
                while batch and not self.cancelled:
                    pending = []
                    for task_id in batch:
                        state = await self.call(
                            activities.chunk_state,
                            {**arg, 'chunk_task': task_id},
                        )
                        if state == 'pending':
                            pending.append(task_id)
                        elif state == 'BLOCKED':
                            await self.call(
                                activities.cancel,
                                {
                                    **arg,
                                    'chunks': self.chunks,
                                    'keep_owner': True,
                                },
                            )
                            return await self.call(
                                activities.complete,
                                {
                                    **arg,
                                    'chunks': self.chunks,
                                    'blocked': True,
                                    'reason': 'review_chunk_blocked',
                                },
                            )
                    batch = pending
                    if workflow.now() >= deadline:
                        self.cancelled = True
                    if batch and not self.cancelled:
                        try:
                            await workflow.wait_condition(
                                lambda: self.cancelled,
                                timeout=timedelta(seconds=15),
                            )
                        except asyncio.TimeoutError:
                            pass
                if self.cancelled:
                    break
            if self.cancelled:
                await self.call(
                    activities.cancel, {**arg, 'chunks': self.chunks}
                )
                return 'CANCELLED'
            return await self.call(
                activities.complete, {**arg, 'chunks': self.chunks}
            )
        except Exception as error:
            reason = 'review_execution_failed'
            if isinstance(error, ActivityError) and isinstance(
                error.cause, ApplicationError
            ):
                reason = error.cause.type or reason
            # Fixed typed failure; credentials/provider exception bodies never enter history.
            await self.call(
                activities.cancel,
                {**arg, 'chunks': self.chunks, 'keep_owner': True},
            )
            return await self.call(
                activities.complete,
                {
                    **arg,
                    'chunks': self.chunks,
                    'blocked': True,
                    'reason': reason,
                },
            )
