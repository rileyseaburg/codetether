"""Finite Job admission and storage ownership, with mocked Kubernetes HTTP."""

import json
import os

from unittest.mock import AsyncMock
from urllib.parse import urlsplit

import asyncpg
import pytest

from a2a_server import forgejo_webhooks
from a2a_server import task_jobs as jobs
from a2a_server.task_jobs import _launch_safely as launch_safely


SHORT_JOB_DEADLINE = 600


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
    assert job['spec']['activeDeadlineSeconds'] == SHORT_JOB_DEADLINE
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
    # This remains true when retained coding Jobs consume their entire cap.
    monkeypatch.setenv('HARVESTER_JOB_MAX_RETAINED', '2')
    job = await jobs.launch(
        {'id': 't', 'metadata': {**base, 'job_readonly': True}}
    )
    assert job is not None and posted
    assert job['metadata']['labels']['codetether.io/job-class'] == 'readonly'
    assert (
        job['spec']['template']['metadata']['labels']
        == job['metadata']['labels']
    )
    assert (
        job['spec']['template']['spec']['containers'][0]['resources'][
            'requests'
        ]['ephemeral-storage']
        == '1Gi'
    )


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
    def __init__(self, rows=()):
        self.sql = []
        self.rows = list(rows)

    async def execute(self, sql, *args):
        self.sql.append(sql)
        return 'UPDATE 1'

    async def fetch(self, sql, *args):
        self.sql.append(sql)
        return self.rows

    async def fetchval(self, sql, *args):
        return True

    def acquire(self):
        conn = self

        class _Ctx:
            async def __aenter__(self):
                return conn

            async def __aexit__(self, *exc):
                return False

        return _Ctx()


@pytest.mark.asyncio
async def test_reconcile_gives_each_lane_a_fair_bounded_window(
    monkeypatch,
):
    """Give terminal cleanup and new work separate bounded scan windows."""
    conn = _Conn(rows=[])
    monkeypatch.setattr(jobs.db, 'get_pool', AsyncMock(return_value=conn))
    await jobs.reconcile()
    scan = next(s for s in conn.sql if 'job_execution' in s and 'ORDER BY' in s)
    assert 'PARTITION BY lane' in scan
    assert "THEN 'cleanup'" in scan and "THEN 'review'" in scan
    assert "ELSE 'coding'" in scan
    assert "COALESCE(metadata->>'job_last_observed_at','')" in scan
    assert 'ordinal<=40' in scan


@pytest.mark.asyncio
async def test_fair_scan_runs_on_real_postgres(monkeypatch):
    """A large terminal backlog cannot crowd out either admission lane."""
    dsn = os.getenv('FORGEJO_INBOX_TEST_DSN', '')
    if not dsn:
        pytest.skip('FORGEJO_INBOX_TEST_DSN not configured')
    assert urlsplit(dsn).hostname in {'127.0.0.1', 'localhost'}
    fake = _Conn()
    monkeypatch.setattr(jobs.db, 'get_pool', AsyncMock(return_value=fake))
    await jobs.reconcile()
    sql = next(s for s in fake.sql if 'WITH candidates' in s)
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute("""CREATE TEMP TABLE tasks (
            id text,status text,metadata jsonb,
            created_at timestamptz DEFAULT now())""")
        records = []
        for index in range(200):
            records.append(
                (
                    f'old-{index}',
                    'completed',
                    json.dumps({'job_execution': True}),
                )
            )
        for lane in ('review', 'coding'):
            for index in range(80):
                records.append(
                    (
                        f'{lane}-{index}',
                        'pending',
                        json.dumps(
                            {
                                'job_execution': True,
                                'job_readonly': lane == 'review',
                            }
                        ),
                    )
                )
        await conn.executemany(
            'INSERT INTO tasks(id,status,metadata) VALUES($1,$2,$3::jsonb)',
            records,
        )
        rows = await conn.fetch(sql)
        expected_lane_size = 40
        for prefix in ('old-', 'coding-', 'review-'):
            assert sum(r['id'].startswith(prefix) for r in rows) == (
                expected_lane_size
            )
        first = {r['id'] for r in rows}
        await conn.execute(
            """UPDATE tasks SET metadata=metadata ||
            jsonb_build_object('job_last_observed_at',now())
            WHERE id=ANY($1::text[])""",
            list(first),
        )
        later = {r['id'] for r in await conn.fetch(sql)}
        assert first.isdisjoint(later)
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_terminal_task_with_absent_job_stops_being_rescanned(monkeypatch):
    conn = _Conn(
        rows=[
            {
                'id': 'gone',
                'status': 'cancelled',
                'metadata': json.dumps({'job_name': 'ct-task-gone'}),
            }
        ]
    )
    monkeypatch.setattr(jobs.db, 'get_pool', AsyncMock(return_value=conn))
    monkeypatch.setattr(jobs, 'kube', AsyncMock(return_value=None))
    await jobs.reconcile()
    assert any(
        'job_cleanup_scheduled' in s and 'job_absent_at_reconcile' in s
        for s in conn.sql
    )


def _terminal_job(name='ct-task-x'):
    return {
        'metadata': {'name': name},
        'status': {'conditions': [{'type': 'Failed', 'status': 'True'}]},
    }


@pytest.mark.asyncio
async def test_cancelled_readonly_review_job_releases_retention_slot(
    monkeypatch,
):
    """A cancelled review chunk must not exhaust admission slots."""
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
async def test_clean_unpublished_work_reclaims_when_base_commit_is_remote(
    monkeypatch,
):
    """An unpublished issue branch can contain only the remote base commit."""
    monkeypatch.setenv('FORGEJO_API_URL', 'https://forge.example/api/v1')
    task = {'metadata': {'repo': 'owner/repo', 'branch_name': 'issue-9'}}
    evidence = [
        {'message': json.dumps({'cleanup_eligible': True, 'head_sha': 'base'})}
    ]

    async def api(method, base, path, **kw):
        if path.endswith('/owner/repo'):
            return {'default_branch': 'main'}
        if path.endswith('/branches/main'):
            return {'commit': {'id': 'base'}}
        if '/branches/' in path:
            return None
        return None

    monkeypatch.setattr(forgejo_webhooks, 'forgejo_json', api)
    assert await jobs.safe_to_reclaim(task, evidence)

    async def unknown(method, base, path, **kw):
        return {'default_branch': 'main'} if path.endswith('/repo') else None

    monkeypatch.setattr(forgejo_webhooks, 'forgejo_json', unknown)
    assert not await jobs.safe_to_reclaim(task, evidence)


@pytest.mark.asyncio
async def test_failed_job_whose_worker_never_started_releases_slot(monkeypatch):
    patches = []

    async def kube(method, path, body=None, missing=False):
        if method == 'PATCH':
            patches.append(body)
        return {
            'items': [
                {
                    'metadata': {'name': 'p'},
                    'status': {
                        'initContainerStatuses': [
                            {
                                'name': 'workspace-prepare',
                                'state': {
                                    'terminated': {
                                        'exitCode': 1,
                                        'reason': 'Error',
                                        'message': (
                                            '{"diagnostic": '
                                            '"workspace_bootstrap_timeout"}'
                                        ),
                                    }
                                },
                            }
                        ],
                        'containerStatuses': [
                            {
                                'name': 'worker',
                                'state': {
                                    'waiting': {'reason': 'PodInitializing'}
                                },
                            }
                        ],
                    },
                }
            ]
        }

    monkeypatch.setattr(jobs, 'kube', kube)
    conn = _Conn()
    task = {
        'id': 'code',
        'status': 'failed',
        'metadata': {'job_readonly': False, 'agent_type': 'build'},
    }
    await jobs.observe_terminal(conn, task, _terminal_job())
    assert patches and 'ttlSecondsAfterFinished' in patches[0]['spec']


@pytest.mark.asyncio
async def test_cancelled_coding_job_is_retained_for_recovery(monkeypatch):
    patches = []

    async def kube(method, path, body=None, missing=False):
        if method == 'PATCH':
            patches.append(body)
        return {
            'items': [
                {
                    'metadata': {'name': 'preserved-pod'},
                    'status': {
                        'containerStatuses': [
                            {
                                'name': 'worker',
                                'state': {
                                    'terminated': {
                                        'exitCode': 1,
                                        'reason': 'Error',
                                        'message': '{"cleanup_eligible":false}',
                                    }
                                },
                            }
                        ]
                    },
                }
            ]
        }

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


@pytest.mark.asyncio
async def test_absent_pod_preserves_audit_and_reclaims_only_job(monkeypatch):
    evidence = [
        {
            'pod': 'old',
            'container': 'worker',
            'message': '{"workspace_clean":false,"unpushed":true}',
        }
    ]
    task = {
        'id': 'gone',
        'status': 'completed',
        'metadata': {'job_readonly': False, 'job_terminal_evidence': evidence},
    }
    conn = AsyncMock()
    api = AsyncMock(return_value={'items': []})
    monkeypatch.setattr(jobs, 'kube', api)
    await jobs.observe_terminal(conn, task, _terminal_job())
    saved = json.loads(conn.execute.await_args_list[0].args[2])
    assert saved['job_terminal_evidence'] == evidence
    assert saved['job_pods_absent'] is True
    assert api.await_args_list[-1].args[0] == 'PATCH'


@pytest.mark.asyncio
async def test_single_branch_clone_verifies_every_head_remotely(monkeypatch):
    base, topic, current = 'a' * 40, 'b' * 40, 'c' * 40
    task = {'metadata': {'repo': 'owner/repo', 'branch_name': 'topic'}}
    audit = {
        'workspace_clean': True,
        'stash_empty': True,
        'unpushed': True,
        'cleanup_eligible': False,
        'audit_diagnostic': 'audit_local_refs_only',
        'local_branch_heads': {
            'refs/heads/main': base,
            'refs/heads/topic': topic,
        },
    }
    evidence = [{'container': 'worker', 'message': json.dumps(audit)}]
    calls = []

    async def remote(method, api_base, path, **kwargs):
        calls.append(path)
        if '/branches/' in path:
            return {'commit': {'id': current}}
        return {'total_commits': 0, 'commits': []}

    monkeypatch.setenv('FORGEJO_API_URL', 'https://forge.example/api/v1')
    monkeypatch.setattr(jobs, '_forgejo_json', remote)
    assert await jobs.safe_to_reclaim(task, evidence)
    assert f'/repos/owner/repo/compare/{current}...{topic}' in calls
    assert f'/repos/owner/repo/compare/{current}...{base}' in calls

    async def unpushed(method, api_base, path, **kwargs):
        if path.endswith('/owner/repo'):
            return {'default_branch': 'main'}
        if '/branches/' in path:
            return {'commit': {'id': current}}
        return {'total_commits': 1, 'commits': [{'sha': topic}]}

    monkeypatch.setattr(jobs, '_forgejo_json', unpushed)
    assert not await jobs.safe_to_reclaim(task, evidence)

    audit['workspace_clean'] = False
    api = AsyncMock()
    monkeypatch.setattr(jobs, '_forgejo_json', api)
    assert not await jobs.safe_to_reclaim(
        task, [{'container': 'worker', 'message': json.dumps(audit)}]
    )
    api.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'reason,terminal',
    [
        ('job_head_advanced', True),
        ('job_pr_closed', True),
        ('job_kubernetes_GET_503', False),
        ('job_retention_capacity_exhausted', False),
    ],
)
async def test_permanent_binding_failure_is_not_queued_forever(
    monkeypatch,
    reason,
    terminal,
):
    """Changed PR heads fail visibly; transient admission limits still defer."""
    conn = AsyncMock()
    conn.execute.return_value = 'UPDATE 1'
    monkeypatch.setattr(
        jobs, 'launch', AsyncMock(side_effect=RuntimeError(reason))
    )
    result, failed = await launch_safely(conn, {'id': 't'})
    assert result is None and failed is terminal
    sql = [c.args[0] for c in conn.execute.await_args_list]
    assert any("SET status='failed'" in s for s in sql) is terminal
