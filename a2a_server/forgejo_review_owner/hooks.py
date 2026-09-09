"""Signed PR events and bounded recovery both attach to the same review owner."""

import asyncio
import logging
import os

from a2a_server import database as db

from . import enabled, ensure_review


_TASK = None


def start_reconciler():
    global _TASK
    if not os.getenv('FORGEJO_SINGLE_REVIEW_REPOS') or (
        _TASK and not _TASK.done()
    ):
        return

    async def loop():
        while True:
            await asyncio.sleep(60)
            try:
                await reconcile()
            except asyncio.CancelledError:
                raise
            except Exception:
                logging.getLogger(__name__).warning(
                    'Single-review reconciliation deferred'
                )

    _TASK = asyncio.create_task(loop())


async def handle_event(payload):
    repo = (payload.get('repository') or {}).get('full_name', '')
    if not enabled(repo):
        return None
    pr = payload.get('pull_request') or {}
    number = int(pr.get('number') or payload.get('number') or 0)
    action = payload.get('action')
    if action == 'review_requested':
        actor = (payload.get('sender') or {}).get('login', '')
        if actor.lower() in {'codetether-bot', 'codetether', 'spotless-agent'}:
            return {'accepted': False, 'reason': 'self-review-request'}
        task_id = await ensure_review(repo, number)
        task = await db.db_get_task(task_id)
        if (
            task['status'] in {'failed', 'cancelled', 'completed'}
            and task['metadata'].get('review_verdict') != 'APPROVED'
        ):
            from a2a_server.temporal.config import get_temporal_client

            client = await get_temporal_client()
            await client.get_workflow_handle(
                task['metadata']['review_workflow_id']
            ).signal(
                'retry', int(task['metadata'].get('review_attempt', 1)) + 1
            )
        return {'accepted': True, 'review_task_id': task_id}
    if not number:
        return {'accepted': False, 'reason': 'invalid-pr'}
    if action in {
        'opened',
        'synchronize',
        'synchronized',
        'reopened',
        'ready_for_review',
    }:
        task_id = await ensure_review(repo, number)
        return {'accepted': True, 'review_task_id': task_id}
    if action == 'closed':
        await cancel_old_reviews(repo, number, None)
    return {'accepted': False, 'reason': 'no-review-action'}


async def cancel_old_reviews(repo, number, current_sha):
    from a2a_server.temporal.config import get_temporal_client

    pool = await db.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT metadata->>'review_workflow_id' AS workflow
            FROM tasks WHERE metadata->>'source'='forgejo-review-owner'
            AND metadata->>'repo'=$1 AND metadata->>'pr_number'=$2
            AND ($3::text IS NULL OR metadata->>'pr_head_sha'!=$3)
            AND status NOT IN ('completed','failed','cancelled')""",
            repo,
            str(number),
            current_sha,
        )
    client = await get_temporal_client()
    for row in rows:
        await client.get_workflow_handle(row['workflow']).signal('cancel')


async def retry_after_checks(task_id):
    """A blocked owner may retry once when previously missing build evidence arrives."""
    from a2a_server.forgejo_automerge import required_checks
    from a2a_server.temporal.config import get_temporal_client

    from .state import endpoint, forgejo_json

    task = await db.db_get_task(task_id)
    meta = task['metadata']
    if task['status'] != 'failed' or meta.get('review_verdict') != 'BLOCKED':
        return
    required = {
        c
        for c in required_checks(meta['repo'])
        if 'codetether' not in c.lower()
    }
    if not required:
        return
    previous = {
        r.get('context'): r.get('status')
        for r in meta.get('review_context', {}).get('ci', [])
    }
    if all(previous.get(c) == 'success' for c in required):
        return
    base, path = endpoint(meta['repo'])
    result = await forgejo_json(
        'GET', base, f'{path}/commits/{meta["pr_head_sha"]}/status?limit=100'
    )
    current = {
        r.get('context'): r.get('status')
        for r in (result.get('statuses') or [])
    }
    if not all(current.get(c) == 'success' for c in required):
        return
    client = await get_temporal_client()
    await client.get_workflow_handle(meta['review_workflow_id']).signal(
        'retry', int(meta.get('review_attempt', 1)) + 1
    )


async def reconcile():
    """Repair missed events only for enrolled PRs, never backfill an entire repository."""
    from .recovery import watch_recoveries

    await watch_recoveries()
    pool = await db.get_pool()
    if pool is None:
        return
    async with pool.acquire() as conn:
        rows = await conn.fetch("""SELECT DISTINCT metadata->>'repo' AS repo,
            metadata->>'pr_number' AS pr FROM tasks
            WHERE metadata->>'source'='forgejo-review-owner' LIMIT 50""")
    for row in rows:
        if not enabled(row['repo']):
            continue
        try:
            task_id = await ensure_review(row['repo'], int(row['pr']))
            await retry_after_checks(task_id)
            from .recovery import ensure_recovery

            await ensure_recovery(task_id)
        except RuntimeError:
            pass
