"""Head binding, durable aggregate records and the sole review status publisher."""

import json
import os

from urllib.parse import quote

from a2a_server import database as db
from a2a_server.forgejo_agent_client import _request
from a2a_server.forgejo_automation_policy import pr_is_paused

from . import STATUS_CONTEXT


async def forgejo_json(method, base, path, payload=None):
    return await _request(method, path, base_url=base, payload=payload)


def endpoint(repo):
    owner, name = repo.split('/', 1)
    return os.environ['FORGEJO_API_URL'].rstrip(
        '/'
    ), f'/repos/{quote(owner, safe="")}/{quote(name, safe="")}'


async def current_pr(repo, number):
    if pr_is_paused(repo, number):
        raise RuntimeError('review_paused')
    base, path = endpoint(repo)
    pr = await forgejo_json('GET', base, f'{path}/pulls/{number}')
    if pr.get('state') != 'open':
        raise RuntimeError('review_pr_closed')
    if (
        pr.get('state') != 'open'
        or pr.get('draft')
        or pr.get('work_in_progress')
        or str(pr.get('title', ''))
        .lower()
        .startswith(('wip:', '[wip]', 'draft:'))
    ):
        raise RuntimeError('review_pr_not_ready')
    return pr


async def bound_pr(arg):
    pr = await current_pr(arg['repo'], arg['pr'])
    if pr['head']['sha'] != arg['sha']:
        raise RuntimeError('review_head_advanced')
    return pr


async def ensure_record(repo, pr, task_id, workflow_id):
    pool = await db.get_pool()
    if pool is None:
        raise RuntimeError('review_storage_unavailable')
    base, _ = endpoint(repo)
    metadata = {
        'source': 'forgejo-review-owner',
        'repo': repo,
        'pr_number': pr['number'],
        'pr_head_sha': pr['head']['sha'],
        'branch_name': pr['head']['ref'],
        'forgejo_api_url': base,
        'workspace_id': 'global',
        'review_workflow_id': workflow_id,
        'review_owner': True,
    }
    async with pool.acquire() as conn:
        # One atomic insert avoids nested pool acquisition while holding a lock.
        await conn.execute(
            """INSERT INTO tasks
            (id,workspace_id,title,prompt,agent_type,status,metadata,created_at,updated_at)
            VALUES($1,NULL,$2,'Server-owned review aggregate','review_aggregate','working',$3::jsonb,NOW(),NOW())
            ON CONFLICT(id) DO NOTHING""",
            task_id,
            f'Review PR #{pr["number"]}',
            json.dumps(metadata),
        )


async def checkpoint(task_id, values):
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            'UPDATE tasks SET metadata=metadata || $2::jsonb, updated_at=NOW() WHERE id=$1',
            task_id,
            json.dumps(values),
        )


async def snapshot(task_id):
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            'SELECT context,chunks FROM forgejo_review_snapshots WHERE owner_task_id=$1',
            task_id,
        )
    if not row:
        return None
    return {
        k: json.loads(row[k]) if isinstance(row[k], str) else row[k]
        for k in ('context', 'chunks')
    }


async def save_snapshot(task_id, context, chunks):
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO forgejo_review_snapshots(owner_task_id,context,chunks)
            VALUES($1,$2::jsonb,$3::jsonb) ON CONFLICT(owner_task_id) DO NOTHING""",
            task_id,
            json.dumps(context),
            json.dumps(chunks),
        )


async def publish_state(arg, state, description):
    """Publish only to the bound commit; never move an old result onto a new head."""
    pr = await bound_pr(arg)
    base, path = endpoint(arg['repo'])
    await forgejo_json(
        'POST',
        base,
        f'{path}/statuses/{arg["sha"]}',
        {
            'state': state,
            'context': STATUS_CONTEXT,
            'description': description[:140],
            'target_url': pr['html_url'],
        },
    )


async def finish(arg, verdict, detail):
    """Publish one full-coverage review. Only APPROVED yields a green status."""
    task = await db.db_get_task(arg['task_id'])
    if task.get('status') == 'cancelled':
        return 'CANCELLED'
    terminal = (
        'completed'
        if verdict in {'APPROVED', 'CHANGES_REQUESTED'}
        else 'failed'
    )
    text = f'{verdict}\n\n{detail}'
    try:
        await bound_pr(arg)
    except RuntimeError:
        await db.db_update_task_status(
            arg['task_id'], 'cancelled', error='review_head_changed_or_paused'
        )
        return 'CANCELLED'
    base, path = endpoint(arg['repo'])
    marker = f'<!-- codetether-review-owner:{arg["task_id"]}:{arg.get("attempt", 1)} -->'
    payload = {
        'body': text + '\n\n' + marker,
        'event': 'COMMENT',
        'commit_id': arg['sha'],
    }
    rows = await forgejo_json(
        'GET', base, f'{path}/pulls/{arg["pr"]}/reviews?limit=100'
    )
    if not any(marker in str(r.get('body', '')) for r in rows):
        await forgejo_json(
            'POST', base, f'{path}/pulls/{arg["pr"]}/reviews', payload
        )
    state = 'success' if verdict == 'APPROVED' else 'failure'
    await publish_state(arg, state, f'Harvester review: {verdict.lower()}')
    await checkpoint(
        arg['task_id'], {'review_verdict': verdict, 'review_published': True}
    )
    await db.db_update_task_status(
        arg['task_id'],
        terminal,
        result=text,
        error=None if terminal == 'completed' else 'review_blocked',
    )
    return verdict
