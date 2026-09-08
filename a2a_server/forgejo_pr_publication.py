"""Publish an issue task's pushed branch without exposing API secrets to models."""
# ruff: noqa: PLC0415, E501

import json
import os

from urllib.parse import quote

from fastapi import HTTPException

from a2a_server.forgejo_automation_policy import pr_is_paused


async def _existing_pr(api, base, path, repo, branch):
    """Search all states; closed PRs must not be silently recreated."""
    seen = set()
    for page in range(1, 101):
        rows = await api(
            'GET', base, f'{path}/pulls?state=all&limit=50&page={page}'
        )
        if not isinstance(rows, list):
            raise RuntimeError('Forgejo PR listing unavailable')
        if not rows:
            return None
        identifiers = {row.get('number') for row in rows}
        if not identifiers - seen:
            raise RuntimeError('Forgejo PR pagination did not advance')
        seen.update(identifiers)
        for row in rows:
            head = row.get('head') or {}
            if (
                head.get('ref') == branch
                and (head.get('repo') or {}).get('full_name') == repo
            ):
                return row
    raise RuntimeError(
        'Forgejo PR search limit reached; refusing duplicate publication'
    )


def _body(number, branch, head_sha, target, task_url, count):
    return (
        f'## Summary\n\nChanges on `{branch}` for issue #{number}.\n\n'
        f'- Remote head: `{head_sha}`\n- Target branch: `{target}`\n'
        f'- Changed files in the remote comparison: {count}\n\n'
        '## Validation\n\n'
        '**Static/local:** the publisher inspected the remote branch and its '
        'non-empty comparison against the target branch.\n\n'
        '**Not-run by the publisher:** compilation, tests, and post-change '
        'runtime verification. This PR does not assert that CI is green.\n\n'
        f'[Worker outcome and validation limitations]({task_url})\n\n'
        f'Refs #{number}.\n\n<!-- codetether-issue-pr:{number} -->'
    )


async def ensure_issue_pull_request(task):
    """Create/reuse one PR for a completed, native issue task's pushed branch.

    This never changes Git refs, grants credentials, marks a task successful,
    or merges a PR. Native request binding and the remote diff are verified
    before publication. Lost responses reconcile by branch on the next call.
    """
    from a2a_server import database
    from a2a_server.forgejo_webhooks import forgejo_json

    meta = task.get('metadata') or {}
    if (
        task.get('status') != 'completed'
        or meta.get('source') != 'forgejo-webhook'
    ):
        return None
    if meta.get('workflow_stage') != 'code' or meta.get('pr_number'):
        return None
    repo = str(meta.get('repo') or '')
    number = int(meta.get('issue_number') or 0)
    native_id = int(meta.get('forgejo_agent_task_id') or 0)
    branch = str(meta.get('branch_name') or '')
    base = str(meta.get('forgejo_api_url') or '').rstrip('/')
    configured = os.getenv('FORGEJO_API_URL', '').rstrip('/')
    if not repo or not number or not native_id or '/' not in repo:
        return None
    if branch != f'codetether/issue-{number}':
        return None
    if not configured or base != configured:
        raise HTTPException(
            503, 'Trusted Forgejo API configuration required for publication'
        )
    if pr_is_paused(repo, number):
        raise HTTPException(
            409, 'Forgejo automation is paused for this request'
        )
    pool = await database.get_pool()
    if pool is None:
        raise HTTPException(503, 'PR publication ownership storage unavailable')
    owner, name = repo.split('/', 1)
    path = f'/repos/{quote(owner, safe="")}/{quote(name, safe="")}'
    lock = f'forgejo-issue-pr:{base}:{repo}:{number}'
    async with pool.acquire() as conn:
        await conn.execute(
            'SELECT pg_advisory_lock(hashtextextended($1,0))', lock
        )
        try:
            native = await forgejo_json(
                'GET', base, f'{path}/agent/tasks/{native_id}'
            )
            if (
                int(native.get('issue_index') or 0) != number
                or native.get('branch') != branch
            ):
                raise HTTPException(
                    409, 'Native request does not authorize this issue branch'
                )
            if native.get('operation') != 'fix':
                return None
            if native.get('status') == 'cancelled':
                return None
            existing = await _existing_pr(
                forgejo_json, base, path, repo, branch
            )
            if existing:
                pr = existing
            else:
                if native.get('status') in {'cancelled', 'completed'}:
                    return None
                issue = await forgejo_json(
                    'GET', base, f'{path}/issues/{number}'
                )
                if issue.get('state') != 'open' or issue.get('pull_request'):
                    return None
                repository = await forgejo_json('GET', base, path)
                target = str(repository.get('default_branch') or '')
                if not target or not repository.get('has_pull_requests'):
                    return None
                remote = await forgejo_json(
                    'GET', base, f'{path}/branches/{quote(branch, safe="")}'
                )
                head_sha = str((remote.get('commit') or {}).get('id') or '')
                comparison = await forgejo_json(
                    'GET',
                    base,
                    f'{path}/compare/{quote(target, safe="")}...{quote(branch, safe="")}',
                )
                commits = comparison.get('commits') or []
                files = comparison.get('files') or []
                if (
                    not head_sha
                    or not files
                    or not any(c.get('sha') == head_sha for c in commits)
                ):
                    return None
                # Check again immediately before POST; never publish knowingly stale evidence.
                remote = await forgejo_json(
                    'GET', base, f'{path}/branches/{quote(branch, safe="")}'
                )
                if (remote.get('commit') or {}).get('id') != head_sha:
                    raise HTTPException(
                        409, 'Issue branch advanced during PR preparation'
                    )
                pr = await forgejo_json(
                    'POST',
                    base,
                    f'{path}/pulls',
                    {
                        'head': branch,
                        'base': target,
                        'title': f'Fix #{number}: {str(issue.get("title") or "issue changes")[:150]}',
                        'body': _body(
                            number,
                            branch,
                            head_sha,
                            target,
                            native['html_url'],
                            len(files),
                        ),
                    },
                )
            if not pr.get('number'):
                raise RuntimeError('Forgejo returned no published PR identity')
            # Separate output checkpoint: never overwrite the task's pinned input head.
            await conn.execute(
                """UPDATE tasks SET metadata = COALESCE(metadata,'{}'::jsonb)
                || jsonb_build_object('forgejo_published_pr', $2::jsonb)
                WHERE id=$1 AND metadata->>'forgejo_agent_task_id'=$3""",
                str(task['id']),
                json.dumps({'number': pr['number'], 'url': pr.get('html_url')}),
                str(native_id),
            )
            return pr
        finally:
            await conn.execute(
                'SELECT pg_advisory_unlock(hashtextextended($1,0))', lock
            )
