"""Fail-closed automatic merging with mocked Forgejo requests."""

import copy
import json

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest

from a2a_server import database, forgejo_webhooks
from a2a_server.forgejo_automerge import (
    changes_requested,
    checks_succeeded,
    maybe_merge,
)


def combined():
    return {
        'sha': 'head',
        'state': 'success',
        'total_count': 2,
        'statuses': [
            {'context': 'build', 'status': 'success'},
            {'context': 'review', 'status': 'success'},
        ],
    }


@pytest.mark.parametrize(
    'case',
    ['failed', 'pending', 'missing', 'wrong-head', 'truncated', 'empty-policy'],
)
def test_checks_fail_closed(case):
    value = combined()
    required = {'build', 'review'}
    if case in {'failed', 'pending'}:
        value['statuses'][0]['status'] = case
    if case == 'missing':
        value['statuses'].pop()
        value['total_count'] = 1
    if case == 'wrong-head':
        value['sha'] = 'old'
    if case == 'truncated':
        value['total_count'] = 3
    if case == 'empty-policy':
        required = set()
    assert not checks_succeeded(value, required, 'head')


def test_latest_substantive_review_is_respected():
    blocked = {'id': 1, 'user': {'id': 5}, 'state': 'REQUEST_CHANGES'}
    assert changes_requested([blocked])
    assert not changes_requested(
        [blocked, {'id': 2, 'user': {'id': 5}, 'state': 'APPROVED'}]
    )


@pytest.fixture
def merge_case(monkeypatch):
    monkeypatch.setenv(
        'FORGEJO_AUTO_MERGE_REQUIRED_CHECKS',
        json.dumps({'owner/repo': ['build', 'review']}),
    )
    monkeypatch.setenv('FORGEJO_API_URL', 'https://forge.example/api/v1')
    monkeypatch.delenv('FORGEJO_AUTOMATION_PAUSED_PRS', raising=False)
    state = {
        'posts': [],
        'managed': '42',
        'move': False,
        'reads': 0,
        'reviews': [],
        'checks': combined(),
        'native_status': 'running',
    }
    state['pr'] = {
        'number': 12,
        'state': 'open',
        'mergeable': True,
        'head': {
            'sha': 'head',
            'ref': 'codetether/issue-9',
            'repo': {'full_name': 'owner/repo'},
        },
        'base': {'ref': 'main'},
    }

    class Conn:
        async def execute(self, *args):
            pass

        async def fetchval(self, *args):
            return state['managed']

    class Pool:
        @asynccontextmanager
        async def acquire(self):
            yield Conn()

    monkeypatch.setattr(database, 'get_pool', AsyncMock(return_value=Pool()))

    async def api(method, base, path, payload=None):
        if method == 'POST':
            state['posts'].append(payload)
            state['pr']['merged'] = True
            return {}
        if '/reviews?' in path:
            return state['reviews'] if 'page=1' in path else []
        if path.endswith('/agent/tasks/42'):
            return {
                'status': state['native_status'],
                'operation': 'fix',
                'issue_index': 9,
                'branch': 'codetether/issue-9',
            }
        if '/status?' in path:
            return state['checks']
        if path.endswith('/pulls/12'):
            state['reads'] += 1
            value = copy.deepcopy(state['pr'])
            if state['move'] and state['reads'] > 1:
                value['head']['sha'] = 'new'
            return value
        assert path == '/repos/owner/repo'
        return {'default_branch': 'main', 'allow_merge_commits': True}

    monkeypatch.setattr(forgejo_webhooks, 'forgejo_json', api)
    return state


@pytest.mark.asyncio
async def test_explicit_merge_is_head_pinned_and_never_forced(merge_case):
    result = await maybe_merge('owner/repo', 12, 9, execute=True)
    assert result['merged']
    assert merge_case['posts'] == [
        {
            'Do': 'merge',
            'head_commit_id': 'head',
            'force_merge': False,
            'merge_when_checks_succeed': False,
            'delete_branch_after_merge': False,
        }
    ]


@pytest.mark.asyncio
async def test_default_mode_does_not_merge(merge_case):
    assert (await maybe_merge('owner/repo', 12, 9))['dry_run']
    assert not merge_case['posts']


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'case',
    [
        'not-managed',
        'moved',
        'paused',
        'checks-failed',
        'draft',
        'conflict',
        'changes-requested',
        'cancelled',
    ],
)
async def test_ineligible_pr_never_posts(merge_case, monkeypatch, case):
    if case == 'not-managed':
        merge_case['managed'] = False
    if case == 'moved':
        merge_case['move'] = True
    if case == 'paused':
        monkeypatch.setenv('FORGEJO_AUTOMATION_PAUSED_PRS', 'owner/repo#12')
    if case == 'checks-failed':
        merge_case['checks']['state'] = 'failure'
    if case == 'draft':
        merge_case['pr']['draft'] = True
    if case == 'conflict':
        merge_case['pr']['mergeable'] = False
    if case == 'changes-requested':
        merge_case['reviews'] = [
            {'id': 1, 'user': {'id': 5}, 'state': 'REQUEST_CHANGES'}
        ]
    if case == 'cancelled':
        merge_case['native_status'] = 'cancelled'
    assert not (await maybe_merge('owner/repo', 12, 9, execute=True))[
        'eligible'
    ]
    assert not merge_case['posts']


@pytest.mark.asyncio
async def test_cutover_requires_own_approved_ledger_and_ignores_only_retired_check(
    merge_case, monkeypatch
):
    monkeypatch.setenv('FORGEJO_SINGLE_REVIEW_REPOS', 'owner/repo')
    retired = {
        'context': 'CodeTether PR Review / CodeTether Review (pull_request_target)',
        'status': 'failure',
    }
    merge_case['checks']['statuses'].append(retired)
    merge_case['checks']['total_count'] = 3
    merge_case['checks']['state'] = 'failure'
    monkeypatch.setattr(database, 'db_get_task', AsyncMock(return_value=None))
    assert (await maybe_merge('owner/repo', 12, 9, execute=True))[
        'reason'
    ] == 'single-review-not-approved'
    assert not merge_case['posts']
    approved = {
        'status': 'completed',
        'metadata': {'review_verdict': 'APPROVED', 'review_published': True},
    }
    monkeypatch.setattr(
        database, 'db_get_task', AsyncMock(return_value=approved)
    )
    merge_case['checks']['statuses'].append(
        {'context': 'additional-security-check', 'status': 'failure'}
    )
    merge_case['checks']['total_count'] = 4
    assert not (await maybe_merge('owner/repo', 12, 9, execute=True))[
        'eligible'
    ]
    assert not merge_case['posts']
    merge_case['checks']['statuses'].pop()
    merge_case['checks']['total_count'] = 3
    assert (await maybe_merge('owner/repo', 12, 9, execute=True))['merged']
