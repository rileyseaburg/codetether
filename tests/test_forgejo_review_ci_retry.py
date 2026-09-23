"""Blocked reviews must re-enter review when CI settles, pass or fail.

Mocked local: database, Forgejo, and Temporal are faked; no live signals.
"""

import json

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest

from a2a_server.forgejo_review_owner import hooks, recovery, state


REQUIRED = {'api-build', 'rust-build'}
NEWEST_PR, CLOSED_PR, HEALTHY_PR = 9, 8, 7


def _checks(**states):
    return [{'context': k, 'status': v} for k, v in states.items()]


FAILED_BUILD = _checks(**{'api-build': 'failure', 'rust-build': 'success'})
GREEN_BUILD = _checks(**{'api-build': 'success', 'rust-build': 'success'})


@pytest.fixture
def owner_case(monkeypatch):
    """One blocked owner whose review saw pending CI, plus fake effects."""
    records = {
        'owner': {
            'id': 'owner',
            'status': 'failed',
            'metadata': {
                'repo': 'owner/repo',
                'pr_number': 7,
                'pr_head_sha': 'head',
                'review_verdict': 'BLOCKED',
                'review_workflow_id': 'review-wf',
                'review_attempt': 1,
                'review_context': {
                    'ci': _checks(
                        **{'api-build': 'pending', 'rust-build': 'pending'}
                    )
                },
            },
        }
    }
    statuses = {'value': []}

    async def get(task_id):
        return records.get(task_id)

    async def mark(task_id, values):
        records[task_id]['metadata'].update(values)

    async def api(method, base, path, payload=None):
        assert path.endswith('/commits/head/status?limit=100')
        return {'statuses': statuses['value']}

    handle = AsyncMock()
    client = AsyncMock()
    client.get_workflow_handle = lambda workflow_id: handle
    monkeypatch.setenv('FORGEJO_API_URL', 'https://forge.example/api/v1')
    monkeypatch.setattr(hooks.db, 'db_get_task', get)
    monkeypatch.setattr(state, 'checkpoint', mark)
    monkeypatch.setattr(state, 'forgejo_json', api)
    monkeypatch.setattr(
        hooks,
        'required_checks',
        lambda repo: {*REQUIRED, 'CodeTether / Harvester Review'},
    )
    monkeypatch.setattr(
        hooks, 'get_temporal_client', AsyncMock(return_value=client)
    )
    return records, statuses, handle


@pytest.mark.asyncio
async def test_settled_failure_reenters_review_once(owner_case):
    """A failed build is concrete evidence the recovery loop can repair."""
    records, statuses, handle = owner_case
    statuses['value'] = FAILED_BUILD
    await hooks.retry_after_checks('owner')
    handle.signal.assert_awaited_once_with('retry', 2)
    signature = json.loads(records['owner']['metadata']['review_checks_retry'])
    assert signature == {'api-build': 'failure', 'rust-build': 'success'}
    await hooks.retry_after_checks('owner')
    handle.signal.assert_awaited_once()


@pytest.mark.asyncio
async def test_settled_success_still_reenters_review(owner_case):
    _, statuses, handle = owner_case
    statuses['value'] = GREEN_BUILD
    await hooks.retry_after_checks('owner')
    handle.signal.assert_awaited_once_with('retry', 2)


@pytest.mark.asyncio
async def test_a_new_settled_result_earns_one_more_retry(owner_case):
    """A rerun that turns failure into success is new evidence."""
    _, statuses, handle = owner_case
    statuses['value'] = FAILED_BUILD
    await hooks.retry_after_checks('owner')
    statuses['value'] = GREEN_BUILD
    await hooks.retry_after_checks('owner')
    assert handle.signal.await_count == len(['failed', 'green'])


@pytest.mark.asyncio
@pytest.mark.parametrize('missing', [True, False])
async def test_unsettled_checks_wait(owner_case, missing):
    _, statuses, handle = owner_case
    states = {'api-build': 'failure'}
    if not missing:
        states['rust-build'] = 'pending'
    statuses['value'] = _checks(**states)
    await hooks.retry_after_checks('owner')
    handle.signal.assert_not_awaited()


@pytest.mark.asyncio
async def test_evidence_the_reviewer_already_judged_is_not_rereviewed(
    owner_case,
):
    records, statuses, handle = owner_case
    records['owner']['metadata']['review_context']['ci'] = FAILED_BUILD
    statuses['value'] = FAILED_BUILD
    await hooks.retry_after_checks('owner')
    handle.signal.assert_not_awaited()


@pytest.mark.asyncio
async def test_active_repair_suppresses_retry(owner_case):
    """The writer's push will start a new-head review; do not race it."""
    records, statuses, handle = owner_case
    records['owner']['metadata']['recovery_task_id'] = 'repair'
    records['repair'] = {'id': 'repair', 'status': 'running', 'metadata': {}}
    statuses['value'] = FAILED_BUILD
    await hooks.retry_after_checks('owner')
    handle.signal.assert_not_awaited()
    records['repair']['status'] = 'completed'
    await hooks.retry_after_checks('owner')
    handle.signal.assert_awaited_once_with('retry', 2)


@pytest.mark.asyncio
async def test_non_blocked_owner_is_untouched(owner_case):
    records, statuses, handle = owner_case
    records['owner']['metadata']['review_verdict'] = 'APPROVED'
    statuses['value'] = FAILED_BUILD
    await hooks.retry_after_checks('owner')
    handle.signal.assert_not_awaited()


@pytest.mark.asyncio
async def test_reconcile_orders_by_recency_and_isolates_failures(monkeypatch):
    """Newest PRs come first; one PR's error cannot starve the others."""
    conn = AsyncMock()
    conn.fetch.return_value = [
        {'repo': 'owner/repo', 'pr': str(n)}
        for n in (NEWEST_PR, CLOSED_PR, HEALTHY_PR)
    ]

    class Pool:
        @asynccontextmanager
        async def acquire(self):
            yield conn

    seen = []

    async def ensure(repo, number):
        seen.append(number)
        if number == NEWEST_PR:
            raise KeyError('head')
        if number == CLOSED_PR:
            raise RuntimeError('review_pr_closed')
        return f'owner-{number}'

    monkeypatch.setenv('FORGEJO_SINGLE_REVIEW_REPOS', 'owner/repo')
    monkeypatch.setattr(hooks.db, 'get_pool', AsyncMock(return_value=Pool()))
    monkeypatch.setattr(hooks, 'ensure_review', ensure)
    retry = AsyncMock()
    monkeypatch.setattr(hooks, 'retry_after_checks', retry)
    monkeypatch.setattr(recovery, 'watch_recoveries', AsyncMock())
    admit = AsyncMock()
    monkeypatch.setattr(recovery, 'ensure_recovery', admit)
    await hooks.reconcile()
    assert seen == [NEWEST_PR, CLOSED_PR, HEALTHY_PR]
    retry.assert_awaited_once_with(f'owner-{HEALTHY_PR}')
    admit.assert_awaited_once_with(f'owner-{HEALTHY_PR}')
    sql = conn.fetch.await_args.args[0]
    assert 'ORDER BY touched DESC' in sql
    assert 'GROUP BY' in sql
