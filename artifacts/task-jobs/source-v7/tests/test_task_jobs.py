"""Finite Job admission and storage ownership, with mocked Kubernetes HTTP."""

import json

from unittest.mock import AsyncMock

import pytest

from a2a_server import task_jobs as jobs


def test_only_opted_in_forgejo_work_is_targeted_to_a_single_job(monkeypatch):
    monkeypatch.setenv('HARVESTER_JOB_REPOS', 'owner/repo')
    meta = {
        'source': 'forgejo-webhook',
        'repo': 'owner/repo',
        'agent_type': 'build',
        'forgejo_work_key': 'attempt:1',
        'target_worker_id': 'old',
        'required_capabilities': ['persistent-workspace'],
    }
    first = jobs.route(meta, 'workspace', 3600)
    second = jobs.route(meta, 'workspace', 3600)
    assert first == second and first['target_agent_name'].startswith('ct-task-')
    assert (
        'target_worker_id' not in first
        and 'task-job' in first['required_capabilities']
    )
    assert not first['job_readonly']
    assert jobs.route({**meta, 'repo': 'another/repo'}, 'workspace', 3600) == {
        **meta,
        'repo': 'another/repo',
    }


@pytest.mark.asyncio
async def test_job_has_no_persistent_workspace_and_cannot_retry_duplicate_work(
    monkeypatch,
):
    monkeypatch.setenv('HARVESTER_JOB_TEMPLATE', 'template')
    meta = {
        'job_name': 'ct-task-test',
        'job_workspace_id': 'ws',
        'job_timeout': 300,
        'job_readonly': False,
        'agent_type': 'clone_repo',
        'required_capabilities': ['task-job'],
    }
    template = {
        'apiVersion': 'batch/v1',
        'kind': 'Job',
        'metadata': {},
        'spec': {
            'template': {
                'metadata': {},
                'spec': {
                    'restartPolicy': 'Never',
                    'containers': [{'env': []}],
                    'volumes': [],
                },
            }
        },
    }
    calls = []

    async def kube(method, path, body=None, missing=False):
        calls.append((method, path, body))
        if method == 'POST':
            return body
        if path.endswith('/ct-task-test'):
            return None
        if 'labelSelector' in path:
            return {'items': []}
        return {'data': {'job.json': json.dumps(template)}}

    monkeypatch.setattr(jobs, 'kube', kube)
    job = await jobs.launch({'id': 'task', 'metadata': meta})
    assert job['spec']['backoffLimit'] == 0
    assert job['spec']['activeDeadlineSeconds'] == 600
    assert job['spec']['template']['spec']['restartPolicy'] == 'Never'
    assert (
        job['spec']['template']['spec']['affinity']['podAntiAffinity'][
            'preferredDuringSchedulingIgnoredDuringExecution'
        ][0]['podAffinityTerm']['topologyKey']
        == 'kubernetes.io/hostname'
    )
    assert job['spec']['template']['spec']['volumes'] == [
        {'name': 'workspace', 'emptyDir': {'sizeLimit': '10Gi'}}
    ]
    assert not any('persistentvolumeclaim' in p.lower() for _, p, _ in calls)


@pytest.mark.asyncio
async def test_readonly_review_jobs_have_their_own_admission_pool(monkeypatch):
    """Long coding clones must not starve PR review indefinitely."""
    monkeypatch.setenv('HARVESTER_JOB_TEMPLATE', 'template')
    monkeypatch.setenv('HARVESTER_JOB_MAX_ACTIVE', '2')
    monkeypatch.setenv('HARVESTER_JOB_MAX_ACTIVE_READONLY', '2')
    template = {
        'metadata': {},
        'spec': {
            'template': {
                'metadata': {},
                'spec': {'containers': [{'env': []}], 'volumes': []},
            }
        },
    }
    coding = {
        'metadata': {
            'name': 'c',
            'labels': {'codetether.io/job-class': 'coding'},
            'annotations': {},
        },
        'status': {'conditions': []},
    }
    posted = []

    async def kube(method, path, body=None, missing=False):
        if method == 'POST':
            posted.append(body)
            return body
        if path.endswith('/ct-task-new'):
            return None
        if 'labelSelector' in path:
            return {
                'items': [
                    coding,
                    {
                        **coding,
                        'metadata': {**coding['metadata'], 'name': 'c2'},
                    },
                ]
            }
        return {'data': {'job.json': json.dumps(template)}}

    monkeypatch.setattr(jobs, 'kube', kube)
    base = {
        'job_name': 'ct-task-new',
        'job_workspace_id': 'ws',
        'job_timeout': 300,
        'required_capabilities': [],
    }
    # Coding pool full: a new coding Job waits.
    assert (
        await jobs.launch(
            {'id': 't', 'metadata': {**base, 'job_readonly': False}}
        )
        is None
    )
    # Read-only pool empty: a review chunk is admitted despite the coding load.
    job = await jobs.launch(
        {'id': 't', 'metadata': {**base, 'job_readonly': True}}
    )
    assert job is not None and posted
    assert job['metadata']['labels']['codetether.io/job-class'] == 'readonly'


@pytest.mark.asyncio
async def test_existing_job_is_never_recreated(monkeypatch):
    api = AsyncMock(return_value={'metadata': {'name': 'existing'}})
    monkeypatch.setattr(jobs, 'kube', api)
    await jobs.launch({'id': 'task', 'metadata': {'job_name': 'existing'}})
    assert api.await_count == 1
    assert api.await_args.args[0] == 'GET'


@pytest.mark.asyncio
async def test_dirty_or_unpushed_work_cannot_be_reclaimed():
    assert not await jobs.safe_to_reclaim(
        {'metadata': {}}, [{'message': json.dumps({'cleanup_eligible': False})}]
    )
    assert not await jobs.safe_to_reclaim(
        {'metadata': {}}, [{'message': 'invalid'}]
    )


@pytest.mark.asyncio
async def test_clean_work_requires_remote_head_confirmation(monkeypatch):
    from a2a_server import forgejo_webhooks

    monkeypatch.setenv('FORGEJO_API_URL', 'https://forge.example/api/v1')
    task = {'metadata': {'repo': 'owner/repo', 'branch_name': 'issue-1'}}
    evidence = [
        {'message': json.dumps({'cleanup_eligible': True, 'head_sha': 'head'})}
    ]
    monkeypatch.setattr(
        forgejo_webhooks,
        'forgejo_json',
        AsyncMock(return_value={'commit': {'id': 'other'}}),
    )
    assert not await jobs.safe_to_reclaim(task, evidence)
    monkeypatch.setattr(
        forgejo_webhooks,
        'forgejo_json',
        AsyncMock(return_value={'commit': {'id': 'head'}}),
    )
    assert await jobs.safe_to_reclaim(task, evidence)


class _Conn:
    def __init__(self):
        self.sql = []

    async def execute(self, sql, *args):
        self.sql.append(sql)
        return 'UPDATE 1'


def _terminal_job(name='ct-task-x'):
    return {
        'metadata': {'name': name},
        'status': {'conditions': [{'type': 'Failed', 'status': 'True'}]},
    }


@pytest.mark.asyncio
async def test_cancelled_readonly_review_job_releases_retention_slot(
    monkeypatch,
):
    """Review chunks hold no user work; a cancelled one must not exhaust admission."""
    patches = []

    async def kube(method, path, body=None, missing=False):
        if method == 'PATCH':
            patches.append(body)
            return body
        return {'items': []}

    monkeypatch.setattr(jobs, 'kube', kube)
    conn = _Conn()
    task = {
        'id': 'chunk',
        'status': 'cancelled',
        'metadata': {'job_readonly': True, 'workflow_stage': 'review_chunk'},
    }
    await jobs.observe_terminal(conn, task, _terminal_job())
    assert patches and 'ttlSecondsAfterFinished' in patches[0]['spec']
    assert any('job_cleanup_scheduled' in s for s in conn.sql)


@pytest.mark.asyncio
async def test_cancelled_coding_job_is_retained_for_recovery(monkeypatch):
    patches = []

    async def kube(method, path, body=None, missing=False):
        if method == 'PATCH':
            patches.append(body)
        return {'items': []}

    monkeypatch.setattr(jobs, 'kube', kube)
    conn = _Conn()
    task = {
        'id': 'code',
        'status': 'cancelled',
        'metadata': {'job_readonly': False, 'agent_type': 'build'},
    }
    await jobs.observe_terminal(conn, task, _terminal_job())
    assert patches == []
    assert not any('job_cleanup_scheduled' in s for s in conn.sql)
