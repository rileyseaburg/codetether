"""Finite Kubernetes Job admission for Forgejo harvester tasks."""

import asyncio
import copy
import hashlib
import json
import logging
import os
import re

from http import HTTPStatus
from importlib import import_module
from pathlib import Path
from urllib.parse import quote

import httpx

from a2a_server import database as db


LOG = logging.getLogger(__name__)
_CONTROLLER = {'task': None}
MAX_AUDIT_BRANCHES = 32


async def _forgejo_json(*args: object, **kwargs: object) -> dict:
    # Webhooks imports task dispatch; defer that import to avoid a cycle.
    return await import_module('a2a_server.forgejo_webhooks').forgejo_json(
        *args, **kwargs
    )


def enabled(metadata):
    """Return whether the repository opted in to finite Job execution."""
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
    """Call Kubernetes without exposing service credentials."""
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
    if missing and r.status_code == HTTPStatus.NOT_FOUND:
        return None
    if r.status_code >= HTTPStatus.BAD_REQUEST:
        raise RuntimeError(f'job_kubernetes_{method}_{r.status_code}')
    return r.json()


def namespace():
    """Return the namespace owning the task Jobs."""
    return os.getenv('HARVESTER_JOB_NAMESPACE', 'a2a-system')


async def bootstrap_env(task):
    """Resolve a fresh clone's pinned repository, branch and head."""
    meta = task['metadata']
    repo = meta['repo']
    base = os.environ['FORGEJO_API_URL'].rstrip('/')
    owner, name = repo.split('/', 1)
    path = f'/repos/{quote(owner, safe="")}/{quote(name, safe="")}'
    data = await _forgejo_json('GET', base, path)
    branch = data['default_branch']
    target = meta.get('branch_name') or branch
    sha = meta.get('pr_head_sha') or ''
    url = data['clone_url']
    if meta.get('pr_number'):
        pr = await _forgejo_json(
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
        existing = await _forgejo_json(
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
    """Admit one idempotent Job, preserving separate review and coding pools."""
    meta = task['metadata']
    name = meta['job_name']
    ns = namespace()
    path = f'/apis/batch/v1/namespaces/{ns}/jobs'
    existing = await kube('GET', path + '/' + name, missing=True)
    if existing:
        return existing
    readonly = bool(meta['job_readonly'])
    active = await kube(
        'GET', path + '?labelSelector=codetether.io%2Ftask-job%3Dtrue'
    )
    retained_coding = [
        j
        for j in active['items']
        if j['metadata'].get('labels', {}).get('codetether.io/job-class')
        != 'readonly'
    ]
    # Retained writer state must not deadlock read-only reviews. Their own
    # active limit and terminal TTL independently bound review storage.
    if not readonly and len(retained_coding) >= int(
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
    # Read-only review Jobs (no clone, 2Gi, minutes) get their own admission
    # pool so multi-GiB coding clones cannot starve PR review indefinitely.
    # Coding Jobs are still bounded by MAX_ACTIVE alone.
    same_class = [
        j
        for j in live
        if (
            j['metadata'].get('labels', {}).get('codetether.io/job-class')
            == 'readonly'
        )
        == readonly
    ]
    limit = int(
        os.getenv(
            'HARVESTER_JOB_MAX_ACTIVE_READONLY'
            if readonly
            else 'HARVESTER_JOB_MAX_ACTIVE',
            '4',
        )
    )
    if len(same_class) >= limit:
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
        'labels': {
            'codetether.io/task-job': 'true',
            'codetether.io/job-class': 'readonly' if readonly else 'coding',
        },
        'annotations': {
            'codetether.io/task-id': task['id'],
            'codetether.io/workspace-id': str(workspace),
        },
    }
    job['spec'].update(
        {'backoffLimit': 0, 'activeDeadlineSeconds': meta['job_timeout'] + 300}
    )
    pod = job['spec']['template']
    pod['metadata'] = {'labels': dict(job['metadata']['labels'])}
    spec = pod['spec']
    container = spec['containers'][0]
    if readonly:
        # Review consumes the pinned diff, not a repository clone/build tree.
        container['resources'] = {
            'requests': {
                'cpu': '250m',
                'memory': '512Mi',
                'ephemeral-storage': '1Gi',
            },
            'limits': {'cpu': '2', 'memory': '2Gi', 'ephemeral-storage': '4Gi'},
        }
        for volume in spec['volumes']:
            if volume['name'] == 'home':
                volume['emptyDir'] = {'sizeLimit': '2Gi'}
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
            else (10 if meta.get('agent_type') == 'clone_repo' else 4)
            * 1024**3,
            'CODETETHER_WORKER_CAPABILITIES': ','.join(
                meta['required_capabilities']
            ),
        }.items()
    ]
    spec['volumes'].append(
        {
            'name': 'workspace',
            # Measured clone ~4.5 GiB; sizeLimit is a per-Job ceiling, not a
            # scheduling reservation (that is the ephemeral-storage request).
            'emptyDir': {
                'sizeLimit': '2Gi' if meta['job_readonly'] else '10Gi'
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
    # Spread Jobs across nodes but do not cap concurrency to one per node:
    # the ephemeral-storage request already reserves each Job's disk budget,
    # and the kubelet evicts on real pressure. HARVESTER_JOB_MAX_ACTIVE is the
    # global concurrency limit.
    spec.setdefault('affinity', {})['podAntiAffinity'] = {
        'preferredDuringSchedulingIgnoredDuringExecution': [
            {
                'weight': 100,
                'podAffinityTerm': {
                    'labelSelector': {
                        'matchLabels': {'codetether.io/task-job': 'true'}
                    },
                    'topologyKey': 'kubernetes.io/hostname',
                },
            }
        ]
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
            'SELECT pg_try_advisory_lock('
            "hashtextextended('codetether-task-job-launch',0))"
        )
        if not lock:
            return
        try:
            rows = await conn.fetch("""WITH candidates AS (
              SELECT id,status,metadata,created_at,
                CASE WHEN status IN ('completed','failed','cancelled')
                     THEN 'cleanup'
                     WHEN metadata->>'job_readonly'='true' THEN 'review'
                     ELSE 'coding' END AS lane
              FROM tasks
                WHERE metadata->>'job_execution'='true'
                AND (metadata->>'job_cleanup_scheduled' IS DISTINCT FROM 'true'
                  OR (metadata->>'job_controller_failed'='true'
                    AND metadata->>'job_failure_notified'
                        IS DISTINCT FROM 'true'))
            ), ranked AS (
              SELECT *, ROW_NUMBER() OVER (
                PARTITION BY lane ORDER BY
                  COALESCE(metadata->>'job_last_observed_at',''),created_at,id
              ) AS ordinal FROM candidates
            )
            SELECT id,status,metadata FROM ranked WHERE ordinal<=40
            ORDER BY CASE lane WHEN 'cleanup' THEN 0
                               WHEN 'review' THEN 1 ELSE 2 END,
                     ordinal""")
            for row in rows:
                task = dict(row)
                task['metadata'] = (
                    json.loads(row['metadata'])
                    if isinstance(row['metadata'], str)
                    else row['metadata']
                )
                await conn.execute(
                    'UPDATE tasks SET metadata=metadata || '
                    "jsonb_build_object('job_last_observed_at', NOW()) "
                    'WHERE id=$1',
                    task['id'],
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
                            'UPDATE tasks SET metadata=metadata || $2::jsonb '
                            'WHERE id=$1',
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
                    if job is None:
                        # Job already gone (TTL, manual release, or never
                        # created before the task ended). Nothing further to
                        # observe; stop rescanning this row every cycle.
                        await conn.execute(
                            'UPDATE tasks SET metadata=metadata || '
                            'jsonb_build_object('
                            "'job_cleanup_scheduled',true,"
                            "'job_absent_at_reconcile',true) "
                            'WHERE id=$1',
                            task['id'],
                        )
                        continue
                if job:
                    await conn.execute(
                        "UPDATE tasks SET metadata=metadata-'job_wait_reason' "
                        'WHERE id=$1',
                        task['id'],
                    )
                    if await _observe_safely(conn, task, job):
                        failures.append(task['id'])
        finally:
            await conn.execute(
                'SELECT pg_advisory_unlock('
                "hashtextextended('codetether-task-job-launch',0))"
            )

    # Completion hooks import dispatch too; resolve them only after releasing
    # the admission lock and its connection.
    notify_forgejo_task_completion = import_module(
        'a2a_server.forgejo_task_completion'
    ).notify_forgejo_task_completion

    for task_id in failures:
        task = await db.db_get_task(task_id)
        await notify_forgejo_task_completion(task)
        async with pool.acquire() as conn:
            await conn.execute(
                'UPDATE tasks SET metadata=metadata || '
                "jsonb_build_object('job_failure_notified',true) "
                'WHERE id=$1',
                task_id,
            )


async def _observe_safely(conn, task, job) -> bool:
    """Keep uncertain work without starving other tasks if an audit fails."""
    try:
        return await observe_terminal(conn, task, job)
    except Exception:
        LOG.warning('Job terminal observation deferred: %s', task['id'])
        return False


async def observe_terminal(conn, task, job):
    """Preserve terminal evidence and reclaim only proven-safe state."""
    done = any(
        c.get('status') == 'True' and c['type'] in ('Complete', 'Failed')
        for c in job.get('status', {}).get('conditions', [])
    )
    if not done:
        return False
    path = (
        f'/api/v1/namespaces/{namespace()}/pods'
        '?labelSelector=batch.kubernetes.io%2Fjob-name%3D'
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
    # Keep the last audit if Kubernetes already garbage-collected its Pod.
    # The remaining terminal Job object itself cannot contain workspace data.
    prior = task['metadata'].get('job_terminal_evidence') or []
    if isinstance(prior, str):
        prior = json.loads(prior)
    if not evidence:
        evidence = prior
    pods_absent = not pods['items']
    await conn.execute(
        'UPDATE tasks SET metadata=metadata || $2::jsonb WHERE id=$1',
        task['id'],
        json.dumps(
            {
                'job_terminal_observed': True,
                'job_terminal_evidence': evidence,
                'job_pods_absent': pods_absent,
            }
        ),
    )
    readonly = task['metadata'].get('job_readonly') or (
        task['metadata'].get('agent_type') == 'clone_repo'
    )
    # Read-only and clone Jobs never hold unpushed user work, so any terminal
    # outcome (including cancelled/failed) may release its retention slot once
    # the evidence above has been persisted. Coding Jobs still need the audit.
    # With no Pods left, deleting the finished Job cannot delete a workspace.
    safe = (readonly or pods_absent) and task['status'] in {
        'completed',
        'failed',
        'cancelled',
    }
    if not safe and task['status'] == 'completed':
        safe = await safe_to_reclaim(task, evidence)
    if not safe and task['status'] in {'failed', 'cancelled'}:
        # The worker container never started (only the workspace-prepare init
        # container terminated), so no agent ever wrote into this workspace.
        # Retaining it would only pin an admission slot.
        safe = _init_failed_before_worker(pods['items'])
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
            'UPDATE tasks SET metadata=metadata || '
            "jsonb_build_object('job_cleanup_scheduled',true) "
            'WHERE id=$1',
            task['id'],
        )
    if task['status'] not in {'completed', 'failed', 'cancelled'}:
        return await _fail_terminated_task(conn, task, evidence)
    return False


def _init_failed_before_worker(pods) -> bool:
    """Require positive failed-init and never-started-worker evidence."""
    return bool(pods) and all(
        any(
            c.get('state', {}).get('terminated', {}).get('exitCode', 0) != 0
            for c in p.get('status', {}).get('initContainerStatuses', [])
        )
        and any(
            c.get('name') == 'worker'
            and c.get('state', {}).get('waiting', {}).get('reason')
            == 'PodInitializing'
            and not c.get('lastState')
            and c.get('restartCount', 0) == 0
            for c in p.get('status', {}).get('containerStatuses', [])
        )
        for p in pods
    )


async def _fail_terminated_task(conn, task, evidence) -> bool:
    """Fail missing worker outcomes without replacing a concurrent success."""
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
        # Do not manufacture success, or overwrite a late terminal update.
        updated = await conn.execute(
            "UPDATE tasks SET status='failed',error=$2,completed_at=NOW(),"
            'metadata=metadata || '
            "jsonb_build_object('job_controller_failed',true) "
            "WHERE id=$1 AND status NOT IN ('completed','failed','cancelled')",
            task['id'],
            failure,
        )
        if updated != 'UPDATE 1':
            return False
        await conn.execute(
            "UPDATE task_runs SET status='failed',completed_at=NOW(),"
            'lease_expires_at=NOW() WHERE task_id=$1 '
            "AND status IN ('queued','running')",
            task['id'],
        )
        return True
    return False


async def _branch_contains(repo_path: str, branch: str, head: str) -> bool:
    """Prove a local commit is reachable from a named remote branch."""
    remote = await _forgejo_json(
        'GET',
        os.environ['FORGEJO_API_URL'],
        f'{repo_path}/branches/{quote(branch, safe="")}',
        allow_not_found=True,
    )
    if not remote:
        return False
    tip = (remote.get('commit') or {}).get('id')
    if tip == head:
        return True
    if not isinstance(tip, str) or not re.fullmatch(r'[0-9a-f]{40,64}', tip):
        return False
    # Forgejo Compare has no merge_base/behind_by field. Reverse the
    # comparison: zero commits reachable from head but not tip proves that
    # head is an ancestor of tip. A commit object's mere existence does not.
    comparison = await _forgejo_json(
        'GET',
        os.environ['FORGEJO_API_URL'],
        f'{repo_path}/compare/{tip}...{head}',
    )
    return (
        comparison.get('total_commits') == 0 and comparison.get('commits') == []
    )


async def _audited_branches_are_remote(meta: dict, result: dict) -> bool:
    """Verify every audited local branch, including single-branch clone refs."""
    heads = result.get('local_branch_heads')
    if (
        not isinstance(heads, dict)
        or not heads
        or len(heads) > MAX_AUDIT_BRANCHES
    ):
        return False
    owner, name = meta['repo'].split('/', 1)
    repo_path = f'/repos/{quote(owner, safe="")}/{quote(name, safe="")}'
    default_branch = None
    for ref, head in heads.items():
        if not isinstance(ref, str) or not ref.startswith('refs/heads/'):
            return False
        if not isinstance(head, str) or not re.fullmatch(
            r'[0-9a-f]{40,64}', head
        ):
            return False
        branch = ref.removeprefix('refs/heads/')
        if await _branch_contains(repo_path, branch, head):
            continue
        # An issue branch might contain no new commits and never be pushed.
        # Only a base commit reachable from the actual default branch is safe.
        if default_branch is None:
            repository = await _forgejo_json(
                'GET', os.environ['FORGEJO_API_URL'], repo_path
            )
            default_branch = repository.get('default_branch') or ''
        if not default_branch or not await _branch_contains(
            repo_path, default_branch, head
        ):
            return False
    return True


async def safe_to_reclaim(task, evidence):
    """Reclaim clean work only after independently checking remote refs."""
    meta = task['metadata']
    try:
        result = next(
            json.loads(e['message'])
            for e in evidence
            if e.get('message') and e.get('container', 'worker') == 'worker'
        )
    except (ValueError, StopIteration):
        return False
    if not isinstance(result, dict):
        return False
    if result.get('local_branch_heads'):
        if (
            result.get('workspace_clean') is not True
            or result.get('stash_empty') is not True
            or result.get('audit_diagnostic') != 'audit_local_refs_only'
        ):
            return False
        # `unpushed` compares cached tracking refs, not the remote. A
        # --single-branch clone tracks main only, even after pushing a topic.
        return await _audited_branches_are_remote(meta, result)
    if result.get('cleanup_eligible') is not True:
        return False
    return await _legacy_audit_is_remote(meta, result)


async def _legacy_audit_is_remote(meta: dict, result: dict) -> bool:
    """Apply the conservative legacy contract without per-branch evidence."""
    branch = meta.get('branch_name')
    head = result.get('head_sha')
    if not branch or not head:
        return False
    owner, name = meta['repo'].split('/', 1)
    repo_path = f'/repos/{quote(owner, safe="")}/{quote(name, safe="")}'
    remote = await _forgejo_json(
        'GET',
        os.environ['FORGEJO_API_URL'],
        f'{repo_path}/branches/{quote(branch, safe="")}',
        allow_not_found=True,
    )
    if remote:
        return remote.get('commit', {}).get('id') == head
    # Preserve conservative behavior for older audits without per-branch heads.
    repository = await _forgejo_json(
        'GET', os.environ['FORGEJO_API_URL'], repo_path
    )
    default_branch = repository.get('default_branch') or ''
    return bool(default_branch) and await _branch_contains(
        repo_path, default_branch, head
    )


def start_controller():
    """Start at most one finite-Job reconciliation loop per API process."""
    running = _CONTROLLER['task']
    if not os.getenv('HARVESTER_JOB_REPOS') or (running and not running.done()):
        return

    async def loop() -> None:
        while True:
            try:
                await reconcile()
            except asyncio.CancelledError:
                raise
            except Exception:
                LOG.exception('Task Job reconciliation failed')
            await asyncio.sleep(15)

    _CONTROLLER['task'] = asyncio.create_task(loop())
