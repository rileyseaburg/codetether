"""Temporal execution proof for the one-owner review workflow (mocked activities)."""

import pytest

from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from a2a_server.forgejo_review_owner.workflow import HeadReviewWorkflow


class Activities:
    def __init__(self, blocked=False):
        self.dispatched = []
        self.completed = []
        self.cancelled = []
        self.blocked = blocked

    @activity.defn(name='forgejo_head_review_prepare')
    async def prepare(self, arg):
        return 3

    @activity.defn(name='forgejo_head_review_chunk')
    async def dispatch(self, arg):
        self.dispatched.append(arg['index'])
        return f'chunk-{arg["index"]}'

    @activity.defn(name='forgejo_head_review_chunk_state')
    async def state(self, arg):
        return 'BLOCKED' if self.blocked else 'APPROVED'

    @activity.defn(name='forgejo_head_review_finish')
    async def finish(self, arg):
        self.completed.append(arg)
        return 'BLOCKED' if arg.get('blocked') else 'APPROVED'

    @activity.defn(name='forgejo_head_review_cancel')
    async def cancel(self, arg):
        self.cancelled.append(arg)

    def all(self):
        return [
            self.prepare,
            self.dispatch,
            self.state,
            self.finish,
            self.cancel,
        ]


@pytest.mark.asyncio
@pytest.mark.parametrize('blocked', [False, True])
async def test_one_owner_finishes_all_chunks_or_fails_closed(blocked):
    fake = Activities(blocked)
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue='single-review-test',
            workflows=[HeadReviewWorkflow],
            activities=fake.all(),
        ):
            result = await env.client.execute_workflow(
                HeadReviewWorkflow.run,
                {
                    'repo': 'owner/repo',
                    'pr': 7,
                    'sha': 'head',
                    'task_id': 'owner',
                },
                id=f'owner-test-{blocked}',
                task_queue='single-review-test',
            )
    assert result == ('BLOCKED' if blocked else 'APPROVED')
    assert fake.dispatched == ([1, 2] if blocked else [1, 2, 3])
    assert len(fake.completed) == 1
    if not blocked:
        assert fake.completed[0]['chunks'] == ['chunk-1', 'chunk-2', 'chunk-3']


@pytest.mark.asyncio
async def test_cancel_before_dispatch_does_not_start_work():
    fake = Activities()
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue='single-review-cancel',
            workflows=[HeadReviewWorkflow],
            activities=fake.all(),
        ):
            handle = await env.client.start_workflow(
                HeadReviewWorkflow.run,
                {
                    'repo': 'owner/repo',
                    'pr': 7,
                    'sha': 'head',
                    'task_id': 'owner',
                },
                id='owner-cancel',
                task_queue='single-review-cancel',
                start_signal='cancel',
                start_signal_args=[],
            )
            result = await handle.result()
    assert result == 'CANCELLED'
    assert not fake.dispatched
    assert fake.cancelled
