"""Finite Kubernetes Job admission for Forgejo harvester tasks."""

import asyncio
import copy
import hashlib
import json
import logging
import os

from pathlib import Path

import httpx

from a2a_server import database as db


LOG = logging.getLogger(__name__)
_LOOP = None


def enabled(metadata):
    repos = {
        s.strip()
        for s in os.getenv('HARVESTER_JOB_REPOS', '').split(',')
        if s.strip()
    }
    return (
        metadata.get('source') == 'forgejo-webhook'
        and metadata.get('repo') in repos
    )


def route(metadata, workspace_id, timeout):
    """Choose a unique worker before task creation/SSE publication can occur."""
    if not enabled(metadata):
        return metadata
    if metadata.get('preserve_session_workspace'):
        raise RuntimeError('job_legacy_session_requires_explicit_handoff')
    key = metadata.get('forgejo_work_key')
    if not key:
        raise RuntimeError('job_task_requires_idempotency_key')
    name = 'ct-task-' + hashlib.sha256(str(key).encode()).hexdigest()[:32]
    readonly = (
        metadata.get('workflow_stage') == 'review_chunk'
        and metadata.get('agent_type') == 'plan'
    )
    caps = set(metadata.get('required_capabilities') or []) | {'task-job'}
    clean = {
        k: v
        for k, v in metadata.items()
        if k not in ('target_worker_id', 'target_agent_name')
    }
    return {
        **clean,
        'job_execution': True,
        'job_name': name,
        'job_readonly': readonly,
        'job_workspace_id': workspace_id,
        'job_timeout': min(int(timeout), 7200),
        'target_agent_name': name,
        'required_capabilities': sorted(caps),
    }


async def kube(method, path, body=None, missing=False):
    token = (
        Path('/var/run/secrets/kubernetes.io/serviceaccount/token')
        .read_text()
        .strip()
    )
    ca = '/var/run/secrets/kubernetes.io/serviceaccount/ca.crt'
    url = (
        'https://'
        + os.environ['KUBERNETES_SERVICE_HOST']
        + ':'
        + os.getenv('KUBERNETES_SERVICE_PORT', '443')
    )
    async with httpx.AsyncClient(verify=ca, timeout=30) as client:
        r = await client.request(
            method,
            url + path,
            headers={
                'Authorization': 'Bearer ' + token,
                'Content-Type': 'application/merge-patch+json'
                if method == 'PATCH'
                else 'application/json',
            },
            json=body,
        )
    if missing and r.status_code == 404:
        return None
    if r.status_code >= 400:
        raise RuntimeError(f'job_kubernetes_{method}_{r.status_code}')
    return r.json()


def namespace():
    return os.getenv('HARVESTER_JOB_NAMESPACE', 'a2a-system')


async def bootstrap_env(task):
    from urllib.parse import quote

    from a2a_server.forgejo_webhooks import forgejo_json

    meta = task['metadata']
    repo = meta['repo']
    base = os.environ['FORGEJO_API_URL'].rstrip('/')
    owner, name = repo.split('/', 1)
    path = f'/repos/{quote(owner, safe="")}/{quote(name, safe="")}'
    data = await forgejo_json('GET', base, path)
    branch = data['default_branch']
    target = meta.get('branch_name') or branch
    sha = meta.get('pr_head_sha') or ''
    url = data['clone_url']
    if meta.get('pr_number'):
        pr = await forgejo_json(
            'GET', base, f'{path}/pulls/{int(meta["pr_number"])}'
        )
        if pr.get('state') != 'open':
            raise RuntimeError('job_pr_closed')
        if sha and pr['head']['sha'] != sha:
            raise RuntimeError('job_head_advanced')
        branch = pr['head']['ref']
        target = branch
        sha = pr['head']['sha']
        if (pr['head'].get('repo') or {}).get('full_name') != repo:
            raise RuntimeError('job_fork_not_authorized')
    else:
        existing = await forgejo_json(
            'GET',
            base,
            path + '/branches/' + quote(target, safe=''),
            allow_not_found=True,
        )
        if existing:
            branch = target
    return [
        {'name': k, 'value': str(v)}
        for k, v in {
            'JOB_WORKSPACE_ID': meta['job_workspace_id'],
            'JOB_GIT_URL': url,
            'JOB_GIT_BRANCH': branch,
            'JOB_TARGET_BRANCH': target,
            'JOB_EXPECTED_HEAD': sha,
        }.items()
    ]


async def launch(task):
    meta = task['metadata']
    name = meta['job_name']
    ns = namespace()
    path = f'/apis/batch/v1/namespaces/{ns}/jobs'
    existing = await kube('GET', path + '/' + name, missing=True)
    if existing:
        return existing
    active = await kube(
        'GET', path + '?labelSelector=codetether.io%2Ftask-job%3Dtrue'
    )
    if len(active['items']) >= int(
        os.getenv('HARVESTER_JOB_MAX_RETAINED', '16')
    ):
        raise RuntimeError('job_retention_capacity_exhausted')
    live = [
        j
        for j in active['items']
        if not any(
            c.get('status') == 'True' and c['type'] in ('Complete', 'Failed')
            for c in j.get('status', {}).get('conditions', [])
        )
    ]
    if len(live) >= int(os.getenv('HARVESTER_JOB_MAX_ACTIVE', '4')):
        return None
    workspace = meta['job_workspace_id']
    if not meta['job_readonly'] and any(
        j['metadata'].get('annotations', {}).get('codetether.io/workspace-id')
        == workspace
        for j in live
    ):
        return None
    cm = await kube(
        'GET',
        f'/api/v1/namespaces/{ns}/configmaps/'
        + os.environ['HARVESTER_JOB_TEMPLATE'],
    )
    job = json.loads(cm['data']['job.json'])
    job['metadata'] = {
        'name': name,
        'labels': {'codetether.io/task-job': 'true'},
        'annotations': {
            'codetether.io/task-id': task['id'],
            'codetether.io/workspace-id': str(workspace),
        },
    }
    job['spec'].update(
        {'backoffLimit': 0, 'activeDeadlineSeconds': meta['job_timeout'] + 300}
    )
    pod = job['spec']['template']
    pod['metadata'] = {'labels': {'codetether.io/task-job': 'true'}}
    spec = pod['spec']
    container = spec['containers'][0]
    root = '/var/lib/codetether/repos'
    container['env'] += [
        {'name': k, 'value': str(v)}
        for k, v in {
            'JOB_TASK_ID': task['id'],
            'JOB_WORKER_NAME': name,
            'JOB_READ_ONLY': 'true' if meta['job_readonly'] else 'false',
            'JOB_WORKSPACE_PATH': root + '/' + str(workspace),
            'JOB_DEADLINE_SECONDS': meta['job_timeout'] + 240,
            'JOB_MIN_FREE_BYTES': 128 * 1024**2
            if meta['job_readonly']
            else (40 if meta.get('agent_type') == 'clone_repo' else 4)
            * 1024**3,
            'CODETETHER_WORKER_CAPABILITIES': ','.join(
                meta['required_capabilities']
            ),
        }.items()
    ]
    spec['volumes'].append(
        {
            'name': 'workspace',
            'emptyDir': {
                'sizeLimit': '2Gi' if meta['job_readonly'] else '40Gi'
            },
        }
    )
    excluded = [
        n.strip()
        for n in os.getenv('HARVESTER_JOB_EXCLUDED_NODES', '').split(',')
        if n.strip()
    ]
    if excluded:
        spec['affinity'] = {
            'nodeAffinity': {
                'requiredDuringSchedulingIgnoredDuringExecution': {
                    'nodeSelectorTerms': [
                        {
                            'matchExpressions': [
                                {
                                    'key': 'kubernetes.io/hostname',
                                    'operator': 'NotIn',
                                    'values': excluded,
                                }
                            ]
                        }
                    ]
                }
            }
        }
    allowed = [
        n.strip()
        for n in os.getenv('HARVESTER_JOB_ALLOWED_NODES', '').split(',')
        if n.strip()
    ]
    if allowed:
        spec['affinity'] = {
            'nodeAffinity': {
                'requiredDuringSchedulingIgnoredDuringExecution': {
                    'nodeSelectorTerms': [
                        {
                            'matchExpressions': [
                                {
                                    'key': 'kubernetes.io/hostname',
                                    'operator': 'In',
                                    'values': allowed,
                                }
                            ]
                        }
                    ]
                }
            }
        }
    if not meta['job_readonly'] and meta.get('agent_type') != 'clone_repo':
        bootstrap = copy.deepcopy(container)
        bootstrap['name'] = 'workspace-prepare'
        bootstrap['command'] = ['python3', '/runner/job_bootstrap.py']
        bootstrap['env'] += await bootstrap_env(task)
        spec['initContainers'] = [bootstrap]
    return await kube('POST', path, job)


async def reconcile():
    """Repair missed launch notifications and project terminal Job failures."""
    pool = await db.get_pool()
    if pool is None:
        return
    failures = []
    async with pool.acquire() as conn:
        lock = await conn.fetchval(
            "SELECT pg_try_advisory_lock(hashtextextended('codetether-task-job-launch',0))"
        )
        if not lock:
            return
        try:
            rows = await conn.fetch("""SELECT id,status,metadata FROM tasks
                WHERE metadata->>'job_execution'='true'
                AND (metadata->>'job_cleanup_scheduled' IS DISTINCT FROM 'true'
                  OR (metadata->>'job_controller_failed'='true' AND metadata->>'job_failure_notified' IS DISTINCT FROM 'true'))
                ORDER BY created_at LIMIT 100""")
            for row in rows:
                task = dict(row)
                task['metadata'] = (
                    json.loads(row['metadata'])
                    if isinstance(row['metadata'], str)
                    else row['metadata']
                )
                if task['metadata'].get('job_controller_failed') and not task[
                    'metadata'
                ].get('job_failure_notified'):
                    failures.append(task['id'])
                    continue
                if task['status'] in {
                    'pending',
                    'queued',
                    'assigned',
                    'running',
                    'working',
                    'in_progress',
                }:
                    try:
                        job = await launch(task)
                    except Exception as error:
                        reason = (
                            str(error)
                            if isinstance(error, RuntimeError)
                            and str(error).startswith('job_')
                            else 'job_launch_failed'
                        )
                        await conn.execute(
                            'UPDATE tasks SET metadata=metadata || $2::jsonb WHERE id=$1',
                            task['id'],
                            json.dumps({'job_wait_reason': reason}),
                        )
                        LOG.warning(
                            'Job launch deferred for %s: %s', task['id'], reason
                        )
                        continue
                else:
                    job = await kube(
                        'GET',
                        f'/apis/batch/v1/namespaces/{namespace()}/jobs/'
                        + task['metadata']['job_name'],
                        missing=True,
                    )
                if job and await observe_terminal(conn, task, job):
                    failures.append(task['id'])
        finally:
            await conn.execute(
                "SELECT pg_advisory_unlock(hashtextextended('codetether-task-job-launch',0))"
            )

    from a2a_server.forgejo_task_completion import (
        notify_forgejo_task_completion,
    )

    for task_id in failures:
        task = await db.db_get_task(task_id)
        await notify_forgejo_task_completion(task)
        async with pool.acquire() as conn:
            await conn.execute(
                'UPDATE tasks SET metadata=metadata || \'{"job_failure_notified":true}\'::jsonb WHERE id=$1',
                task_id,
            )


async def observe_terminal(conn, task, job):
    done = any(
        c.get('status') == 'True' and c['type'] in ('Complete', 'Failed')
        for c in job.get('status', {}).get('conditions', [])
    )
    if not done:
        return
    path = (
        f'/api/v1/namespaces/{namespace()}/pods?labelSelector=batch.kubernetes.io%2Fjob-name%3D'
        + job['metadata']['name']
    )
    pods = await kube('GET', path)
    evidence = []
    for pod in pods['items']:
        for c in [
            *pod.get('status', {}).get('initContainerStatuses', []),
            *pod.get('status', {}).get('containerStatuses', []),
        ]:
            terminal = c.get('state', {}).get('terminated') or {}
            if terminal:
                evidence.append(
                    {
                        'pod': pod['metadata']['name'],
                        'container': c['name'],
                        'exit_code': terminal.get('exitCode'),
                        'reason': terminal.get('reason'),
                        'message': terminal.get('message', '')[:4096],
                    }
                )
    await conn.execute(
        'UPDATE tasks SET metadata=metadata || $2::jsonb WHERE id=$1',
        task['id'],
        json.dumps(
            {'job_terminal_observed': True, 'job_terminal_evidence': evidence}
        ),
    )
    safe = task['status'] == 'completed' and (
        task['metadata'].get('job_readonly')
        or task['metadata'].get('agent_type') == 'clone_repo'
    )
    if not safe and task['status'] == 'completed':
        safe = await safe_to_reclaim(task, evidence)
    if safe:
        await kube(
            'PATCH',
            f'/apis/batch/v1/namespaces/{namespace()}/jobs/'
            + job['metadata']['name'],
            {
                'spec': {
                    'ttlSecondsAfterFinished': int(
                        os.getenv('HARVESTER_JOB_TTL', '900')
                    )
                }
            },
        )
        await conn.execute(
            'UPDATE tasks SET metadata=metadata || \'{"job_cleanup_scheduled":true}\'::jsonb WHERE id=$1',
            task['id'],
        )
    if task['status'] not in {'completed', 'failed', 'cancelled'}:
        diagnostics = []
        for item in evidence:
            try:
                diagnostic = json.loads(item.get('message') or '{}').get(
                    'diagnostic'
                )
            except (ValueError, AttributeError):
                continue
            if diagnostic in {
                'workspace_storage_insufficient',
                'workspace_storage_exhausted',
                'workspace_git_auth_failed',
                'remote_head_advanced',
                'workspace_bootstrap_failed',
                'workspace_bootstrap_timeout',
                'job_storage_insufficient',
                'worker_start_failed',
                'worker_exited_before_terminal',
                'job_deadline_exceeded',
            }:
                diagnostics.append(diagnostic)
        failure = 'kubernetes_job_terminated' + (
            ':' + ','.join(diagnostics) if diagnostics else ''
        )
        # The controller must not manufacture a worker success when the pod disappears.
        await conn.execute(
            "UPDATE tasks SET status='failed',error=$2,completed_at=NOW(),metadata=metadata || '{\"job_controller_failed\":true}'::jsonb WHERE id=$1 AND status NOT IN ('completed','failed','cancelled')",
            task['id'],
            failure,
        )
        await conn.execute(
            "UPDATE task_runs SET status='failed',completed_at=NOW(),lease_expires_at=NOW() WHERE task_id=$1 AND status IN ('queued','running')",
            task['id'],
        )
        return True


async def safe_to_reclaim(task, evidence):
    """Reclaim only clean work whose head is independently verified on the remote."""
    meta = task['metadata']
    try:
        result = next(
            json.loads(e['message'])
            for e in evidence
            if e.get('message') and e.get('container', 'worker') == 'worker'
        )
    except (ValueError, StopIteration):
        return False
    if result.get('cleanup_eligible') is not True:
        return False
    branch = meta.get('branch_name')
    head = result.get('head_sha')
    if not branch or not head:
        return False
    from urllib.parse import quote

    from a2a_server.forgejo_webhooks import forgejo_json

    owner, name = meta['repo'].split('/', 1)
    remote = await forgejo_json(
        'GET',
        os.environ['FORGEJO_API_URL'],
        f'/repos/{quote(owner, safe="")}/{quote(name, safe="")}/branches/{quote(branch, safe="")}',
        allow_not_found=True,
    )
    return bool(remote) and remote.get('commit', {}).get('id') == head


def start_controller():
    global _LOOP
    if not os.getenv('HARVESTER_JOB_REPOS') or (_LOOP and not _LOOP.done()):
        return

    async def loop():
        while True:
            try:
                await reconcile()
            except asyncio.CancelledError:
                raise
            except Exception:
                LOG.exception('Task Job reconciliation failed')
            await asyncio.sleep(15)

    _LOOP = asyncio.create_task(loop())
