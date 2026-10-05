"""Mocked-local coverage for trusted publication of already-pushed issue work."""
# ruff: noqa: PLC0415, PLR2004, SLF001, E501

import asyncio
import copy
import json

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest

from fastapi import HTTPException
from test_forgejo_automation_safety import writer_db  # noqa: F401

from a2a_server import database, forgejo_webhooks
from a2a_server.forgejo_pr_publication import ensure_issue_pull_request


BASE = 'https://forge.example/api/v1'
REPO = 'owner/repo'
BRANCH = 'codetether/issue-9'
SHA = 'a' * 40


@pytest.fixture
def publication(monkeypatch):
    monkeypatch.setenv('FORGEJO_API_URL', BASE)
    monkeypatch.delenv('FORGEJO_AUTOMATION_PAUSED_PRS', raising=False)
    state = {
        'pulls': [],
        'posts': [],
        'updates': [],
        'requests': [],
        'lost_ack': False,
        'native_status': 'failed',
        'empty': False,
        'head_reads': 0,
        'move_head': False,
    }
    mutex = asyncio.Lock()

    class Connection:
        async def execute(self, sql, *args):
            if 'pg_advisory_unlock' in sql:
                mutex.release()
            elif 'pg_advisory_lock' in sql:
                await mutex.acquire()
            else:
                state['updates'].append(args)

    class Pool:
        @asynccontextmanager
        async def acquire(self):
            yield Connection()

    async def api(method, base, path, payload=None, *, allow_not_found=False):
        assert base == BASE
        state['requests'].append((method, path))
        if path.endswith('/agent/tasks/42'):
            return {
                'id': 42,
                'issue_index': 9,
                'branch': BRANCH,
                'operation': 'fix',
                'status': state['native_status'],
                'html_url': 'https://forge.example/owner/repo/agent/tasks/42',
            }
        if '/commits/' in path and path.endswith('/pull'):
            assert allow_not_found
            return copy.deepcopy(state['pulls'][0]) if state['pulls'] else None
        if '/pulls?' in path:
            return copy.deepcopy(state['pulls']) if 'page=1' in path else []
        if path.endswith('/issues/9'):
            return {'state': 'open', 'title': 'Fix the mapper'}
        if path.endswith('/branches/codetether%2Fissue-9'):
            state['head_reads'] += 1
            return {
                'commit': {
                    'id': 'b' * 40
                    if state['move_head'] and state['head_reads'] > 1
                    else SHA
                }
            }
        if '/compare/' in path:
            return {
                'commits': [{'sha': SHA}],
                'files': [] if state['empty'] else [{'filename': 'mapper.rs'}],
            }
        if path.endswith('/pulls') and method == 'POST':
            state['posts'].append(payload)
            pr = {
                'number': 12,
                'state': 'open',
                'head': {
                    'ref': BRANCH,
                    'sha': SHA,
                    'repo': {'full_name': REPO},
                },
                'html_url': 'https://forge.example/owner/repo/pulls/12',
            }
            state['pulls'].append(pr)
            if state['lost_ack']:
                state['lost_ack'] = False
                raise RuntimeError('response lost after server created PR')
            return pr
        assert path == '/repos/owner/repo'
        return {'default_branch': 'main', 'has_pull_requests': True}

    monkeypatch.setattr(database, 'get_pool', AsyncMock(return_value=Pool()))
    monkeypatch.setattr(forgejo_webhooks, 'forgejo_json', api)
    task = {
        'id': 'code-1',
        'status': 'completed',
        'result': 'private narration and credentials must not be copied',
        'metadata': {
            'source': 'forgejo-webhook',
            'repo': REPO,
            'issue_number': 9,
            'forgejo_agent_task_id': 42,
            'workflow_stage': 'code',
            'branch_name': BRANCH,
            'forgejo_api_url': BASE,
            'pr_head_sha': 'original-checkpoint',
        },
    }
    return task, state


@pytest.mark.asyncio
async def test_publishes_verified_branch_without_claiming_ci_success(
    publication,
):
    task, state = publication
    pr = await ensure_issue_pull_request(task)
    assert pr['number'] == 12
    assert len(state['posts']) == 1
    assert state['updates']


@pytest.mark.asyncio
async def test_real_postgres_serializes_publication_and_checkpoints_output(
    publication,
    writer_db,  # noqa: F811 (imported pytest fixture)
):
    task, state = publication
    async with writer_db.acquire() as conn:
        await conn.execute(
            "INSERT INTO tasks(id,status,agent_type,metadata) VALUES($1,'completed','build',$2::jsonb)",
            task['id'],
            json.dumps(task['metadata']),
        )
    results = await asyncio.gather(
        *(ensure_issue_pull_request(task) for _ in range(4))
    )
    assert {r['number'] for r in results} == {12}
    assert len(state['posts']) == 1
    async with writer_db.acquire() as conn:
        stored = await conn.fetchval(
            'SELECT metadata FROM tasks WHERE id=$1', task['id']
        )
    stored = json.loads(stored)
    assert stored['forgejo_published_pr']['number'] == 12
    assert stored['pr_head_sha'] == 'original-checkpoint'
    body = state['posts'][0]['body']
    assert '**Not-run by the publisher:**' in body
    assert SHA in body and 'Refs #9' in body
    assert task['result'] not in body
    assert task['metadata']['pr_head_sha'] == 'original-checkpoint'


@pytest.mark.asyncio
async def test_concurrent_callbacks_create_only_one_pr(publication):
    task, state = publication
    results = await asyncio.gather(
        *(ensure_issue_pull_request(task) for _ in range(8))
    )
    assert {r['number'] for r in results} == {12}
    assert len(state['posts']) == 1


@pytest.mark.asyncio
async def test_lost_post_response_reconciles_without_reposting(publication):
    task, state = publication
    state['lost_ack'] = True
    with pytest.raises(RuntimeError, match='response lost'):
        await ensure_issue_pull_request(task)
    assert (await ensure_issue_pull_request(task))['number'] == 12
    assert len(state['posts']) == 1


@pytest.mark.asyncio
async def test_closed_pr_is_not_reopened(publication):
    task, state = publication
    state['pulls'] = [
        {
            'number': 7,
            'state': 'closed',
            'head': {'ref': BRANCH, 'repo': {'full_name': REPO}},
        }
    ]
    assert (await ensure_issue_pull_request(task))['state'] == 'closed'
    assert not state['posts']


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'case',
    [
        'cancelled',
        'empty',
        'moved',
        'untrusted-base',
        'unowned-branch',
        'paused',
    ],
)
async def test_publication_safety_gates(publication, monkeypatch, case):
    task, state = publication
    if case == 'cancelled':
        state['native_status'] = 'cancelled'
    if case == 'empty':
        state['empty'] = True
    if case == 'moved':
        state['move_head'] = True
    if case == 'untrusted-base':
        task['metadata']['forgejo_api_url'] = 'https://evil.example/api/v1'
    if case == 'unowned-branch':
        task['metadata']['branch_name'] = 'main'
    if case == 'paused':
        monkeypatch.setenv('FORGEJO_AUTOMATION_PAUSED_PRS', 'owner/repo#9')
    if case in {'moved', 'untrusted-base', 'paused'}:
        with pytest.raises(HTTPException):
            await ensure_issue_pull_request(task)
    else:
        assert await ensure_issue_pull_request(task) is None
    assert not state['posts']


@pytest.mark.asyncio
async def test_noncompleted_task_never_touches_provider(publication):
    task, state = publication
    task['status'] = 'failed'
    assert await ensure_issue_pull_request(task) is None
    assert not state['requests']


@pytest.mark.asyncio
async def test_review_pipeline_uses_server_published_pr(
    publication, monkeypatch
):
    from a2a_server import forgejo_automation as automation

    task, state = publication
    task['metadata']['workspace_id'] = 'workspace-1'
    monkeypatch.setattr(
        automation, '_task_exists', AsyncMock(return_value=False)
    )
    dispatch = AsyncMock(return_value='review-1')
    monkeypatch.setattr(
        'a2a_server.persistent_worker_pool.create_and_dispatch_task', dispatch
    )
    monkeypatch.setattr(
        'a2a_server.forgejo_agent_client.update_task', AsyncMock()
    )
    assert await automation.create_forgejo_review_task(task) == 'review-1'
    assert dispatch.await_args.kwargs['metadata']['pr_number'] == 12
    assert len(state['posts']) == 1
