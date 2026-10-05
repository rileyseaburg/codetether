"""Feedback recovery must produce verified progress, not another unbounded writer."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest

from a2a_server.forgejo_review_owner import recovery


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'reason',
    [
        'review_diff_empty',
        'review_diff_size_out_of_bounds',
        'review_capture_failed',
    ],
)
async def test_harness_failures_never_dispatch_application_edits(
    recovery_case, reason
):
    owner, pr, rows, records, dispatch = recovery_case
    owner['metadata']['review_error_reason'] = reason
    assert await recovery.ensure_recovery('owner', ownership_held=True) is None
    dispatch.assert_not_awaited()


def test_empty_diff_is_not_reported_as_oversized():
    from a2a_server.forgejo_review_owner.evidence import split_diff

    with pytest.raises(ValueError, match='^review_diff_empty$'):
        split_diff(b'')


@pytest.fixture
def recovery_case(monkeypatch):
    owner = {
        'id': 'owner',
        'status': 'failed',
        'result': 'BLOCKED: missing exact-head tests',
        'metadata': {
            'repo': 'owner/repo',
            'pr_number': 7,
            'pr_head_sha': 'old',
            'branch_name': 'codetether/issue-6',
            'review_verdict': 'BLOCKED',
            'review_workflow_id': 'review-workflow',
            'review_attempt': 1,
            'review_context': {'ci': []},
        },
    }
    pr = {
        'state': 'open',
        'head': {
            'sha': 'old',
            'ref': 'codetether/issue-6',
            'repo': {'full_name': 'owner/repo'},
        },
    }
    source = {
        'workspace_id': 'workspace',
        'metadata': {'issue_number': 6, 'forgejo_agent_task_id': 42},
    }
    rows = []
    records = {'owner': owner}
    conn = AsyncMock()
    conn.fetch.return_value = rows

    class Pool:
        @asynccontextmanager
        async def acquire(self):
            yield conn

    async def get(task_id):
        return records.get(task_id)

    async def mark(task_id, values):
        records[task_id]['metadata'].update(values)

    monkeypatch.setenv('FORGEJO_REVIEW_RECOVERY_REPOS', 'owner/repo')
    monkeypatch.setenv('FORGEJO_SINGLE_REVIEW_REPOS', 'owner/repo')
    monkeypatch.setenv('FORGEJO_API_URL', 'https://forge.example/api/v1')
    monkeypatch.setattr(recovery.db, 'get_pool', AsyncMock(return_value=Pool()))
    monkeypatch.setattr(recovery.db, 'db_get_task', get)
    monkeypatch.setattr(
        recovery.db, 'db_update_task_status', AsyncMock(return_value=True)
    )
    monkeypatch.setattr(recovery, 'checkpoint', mark)
    monkeypatch.setattr(recovery, 'bound_pr', AsyncMock(return_value=pr))
    monkeypatch.setattr(
        recovery, '_managed_source', AsyncMock(return_value=source)
    )
    monkeypatch.setattr(
        recovery,
        'native_task',
        AsyncMock(
            return_value={
                'operation': 'fix',
                'status': 'failed',
                'issue_index': 6,
                'branch': 'codetether/issue-6',
            }
        ),
    )
    monkeypatch.setattr(recovery, 'pr_is_paused', lambda *args: False)
    from a2a_server import persistent_worker_pool

    dispatch = AsyncMock(return_value='repair')
    monkeypatch.setattr(
        persistent_worker_pool, 'create_and_dispatch_task', dispatch
    )
    return owner, pr, rows, records, dispatch


@pytest.mark.asyncio
async def test_blocked_feedback_dispatches_coding_not_readonly_worker(
    recovery_case,
):
    owner, pr, rows, records, dispatch = recovery_case
    assert (
        await recovery.ensure_recovery('owner', ownership_held=True) == 'repair'
    )
    args = dispatch.await_args.kwargs
    assert args['agent_type'] == 'build'
    assert args['workspace_id'] == 'workspace'
    assert args['metadata']['workflow_stage'] == 'review_recovery'
    assert args['metadata']['required_capabilities'] == ['persistent-workspace']
    assert 'empty commits' in args['prompt']
    assert 'missing or pending' in args['prompt']


@pytest.mark.asyncio
async def test_duplicate_feedback_attaches_to_same_writer(recovery_case):
    owner, pr, rows, records, dispatch = recovery_case
    records['repair'] = {
        'id': 'repair',
        'status': 'running',
        'metadata': {'review_owner_id': 'owner', 'recovery_review_attempt': 1},
    }
    rows.append(records['repair'])
    assert (
        await recovery.ensure_recovery('owner', ownership_held=True) == 'repair'
    )
    dispatch.assert_not_awaited()


@pytest.mark.asyncio
async def test_other_active_writer_and_cross_head_budget_prevent_new_work(
    recovery_case,
):
    owner, pr, rows, records, dispatch = recovery_case
    rows.append(
        {
            'id': 'other',
            'status': 'running',
            'metadata': {'review_owner_id': 'old-owner'},
        }
    )
    assert await recovery.ensure_recovery('owner', ownership_held=True) is None
    rows[:] = [
        {
            'id': str(i),
            'status': 'completed',
            'metadata': {'review_owner_id': 'old-owner'},
        }
        for i in range(3)
    ]
    assert await recovery.ensure_recovery('owner', ownership_held=True) is None
    assert (
        owner['metadata']['recovery_blocker'] == 'recovery_attempts_exhausted'
    )
    dispatch.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'reason', ['unmanaged', 'cancelled', 'approved', 'wrong_branch']
)
async def test_writer_boundaries(recovery_case, monkeypatch, reason):
    owner, pr, rows, records, dispatch = recovery_case
    if reason == 'unmanaged':
        monkeypatch.setattr(
            recovery, '_managed_source', AsyncMock(return_value=None)
        )
    elif reason == 'cancelled':
        monkeypatch.setattr(
            recovery,
            'native_task',
            AsyncMock(return_value={'status': 'cancelled'}),
        )
    elif reason == 'approved':
        owner['metadata']['review_verdict'] = 'APPROVED'
    else:
        pr['head']['ref'] = 'someone-elses-branch'
    assert await recovery.ensure_recovery('owner', ownership_held=True) is None
    dispatch.assert_not_awaited()


@pytest.mark.asyncio
async def test_reported_completion_without_commit_or_checks_is_not_progress(
    recovery_case, monkeypatch
):
    from a2a_server import forgejo_automerge

    owner, pr, rows, records, dispatch = recovery_case
    records['repair'] = {
        'status': 'completed',
        'result': 'I fixed it',
        'metadata': {},
    }
    monkeypatch.setattr(
        forgejo_automerge, 'required_checks', lambda repo: {'build'}
    )
    api = AsyncMock(side_effect=[pr, {'statuses': []}])
    monkeypatch.setattr(recovery, 'forgejo_json', api)
    review = AsyncMock()
    monkeypatch.setattr(recovery, 'ensure_review', review)
    await recovery.reconcile_recovery(owner, 'repair')
    assert (
        owner['metadata']['recovery_blocker']
        == 'no_verified_commit_or_validation'
    )
    review.assert_not_awaited()


@pytest.mark.asyncio
async def test_new_remote_commit_reenters_same_review_owner_system(
    recovery_case, monkeypatch
):
    owner, pr, rows, records, dispatch = recovery_case
    pr['head']['sha'] = 'new'
    records['repair'] = {'status': 'completed', 'metadata': {}}
    monkeypatch.setattr(
        recovery,
        'forgejo_json',
        AsyncMock(
            side_effect=[
                pr,
                {
                    'files': [{'filename': 'test.py'}],
                    'commits': [{'parents': [{'sha': 'old'}]}],
                },
            ]
        ),
    )
    review = AsyncMock(return_value='next-owner')
    monkeypatch.setattr(recovery, 'ensure_review', review)
    await recovery.reconcile_recovery(owner, 'repair')
    review.assert_awaited_once_with('owner/repo', 7, expected_sha='new')
    assert owner['metadata']['recovery_state'] == 'new_head_review'


@pytest.mark.asyncio
async def test_new_green_validation_retries_same_head_without_empty_commit(
    recovery_case, monkeypatch
):
    from a2a_server import forgejo_automerge
    from a2a_server.temporal import config

    owner, pr, rows, records, dispatch = recovery_case
    records['repair'] = {
        'status': 'completed',
        'metadata': {'recovery_review_attempt': 1},
    }
    monkeypatch.setattr(
        forgejo_automerge, 'required_checks', lambda repo: {'build'}
    )
    monkeypatch.setattr(
        recovery,
        'forgejo_json',
        AsyncMock(
            side_effect=[
                pr,
                {'statuses': [{'context': 'build', 'status': 'success'}]},
            ]
        ),
    )
    client = AsyncMock()
    handle = AsyncMock()
    client.get_workflow_handle = lambda _: handle
    monkeypatch.setattr(
        config, 'get_temporal_client', AsyncMock(return_value=client)
    )
    await recovery.reconcile_recovery(owner, 'repair')
    handle.signal.assert_awaited_once_with('retry', 2)
    assert owner['metadata']['recovery_state'] == 'validation_review'
