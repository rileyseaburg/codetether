"""Replay-safe repository planning and acknowledgement for durable intake."""
# Lazy imports avoid the webhook cycle; SQL remains readable.
# ruff: noqa: PLC0415, E501

from urllib.parse import quote

from a2a_server.github_app.mention import is_fix_request


COMMENT_PAGE_SIZE = 100


async def prepare_plan(ctx, base):
    """Resolve a PR head once so later retries cannot target a different commit."""
    from a2a_server.forgejo_webhooks import forgejo_json

    owner, name = ctx['repo'].split('/', 1)
    path = f'/repos/{quote(owner, safe="")}/{quote(name, safe="")}'
    repo = await forgejo_json('GET', base, path)
    branch = str(repo.get('default_branch') or 'main')
    head_sha = ''
    if ctx['is_pr']:
        pr = await forgejo_json('GET', base, f'{path}/pulls/{ctx["number"]}')
        head = pr.get('head') or {}
        branch = str(head.get('ref') or branch)
        head_sha = str(head.get('sha') or '')
    return {
        'repo_data': {'clone_url': repo.get('clone_url')},
        'default_branch': str(repo.get('default_branch') or 'main'),
        'branch': branch,
        'head_sha': head_sha,
    }


async def dispatch(ctx, base, plan):
    """Reuse immutable work keys, deferring unrelated active work, never losing it."""
    from a2a_server.forgejo_webhooks import _dispatch

    if not is_fix_request(ctx['body']):
        return {'accepted': False, 'reason': 'non-fix mention'}
    return await _dispatch({**ctx, '_dispatch_plan': plan}, base)


async def ensure_issue_idle(conn, row, ctx, base):
    """Keep FIFO ownership until the previous native workflow is terminal."""
    from a2a_server.forgejo_agent_client import get_task

    if not is_fix_request(ctx['body']):
        return
    earlier = await conn.fetchval(
        """
        SELECT delivery_id FROM forgejo_webhook_inbox
        WHERE api_base = $1 AND context->>'repo' = $2 AND context->>'number' = $3
            AND (received_at, delivery_id) < ($4, $5)
            AND state != 'acknowledged' LIMIT 1
    """,
        base,
        ctx['repo'],
        str(ctx['number']),
        row['received_at'],
        row['delivery_id'],
    )
    if earlier:
        raise RuntimeError('forgejo_issue_busy')
    previous = await conn.fetchval(
        """
        SELECT native_task_id FROM forgejo_webhook_inbox
        WHERE api_base = $1 AND context->>'repo' = $2 AND context->>'number' = $3
            AND (received_at, delivery_id) < ($4, $5) AND native_task_id IS NOT NULL
        ORDER BY received_at DESC, delivery_id DESC LIMIT 1
    """,
        base,
        ctx['repo'],
        str(ctx['number']),
        row['received_at'],
        row['delivery_id'],
    )
    if previous:
        task = await get_task(repo=ctx['repo'], task_id=previous, base_url=base)
        if task.get('status') not in {'completed', 'failed', 'cancelled'}:
            raise RuntimeError('forgejo_issue_busy')
    busy = await conn.fetchval(
        """
        SELECT id FROM tasks WHERE status IN ('pending', 'queued', 'running', 'in_progress')
            AND metadata->>'source' = 'forgejo-webhook'
            AND metadata->>'repo' = $1 AND metadata->>'issue_number' = $2
            AND ($3::text IS NULL OR metadata->>'forgejo_agent_task_id' IS DISTINCT FROM $3)
        LIMIT 1
    """,
        ctx['repo'],
        str(ctx['number']),
        str(row['native_task_id']) if row['native_task_id'] else None,
    )
    if busy:
        raise RuntimeError('forgejo_issue_busy')


async def bind_native(identity, task_id):
    """Checkpoint the native ID before starting any execution workflow."""
    from a2a_server.forgejo_inbox import pool

    db = await pool()
    async with db.acquire() as conn:
        await conn.execute(
            """
            UPDATE forgejo_webhook_inbox SET native_task_id = $2,
                updated_at = now() WHERE delivery_id = $1
        """,
            identity,
            task_id,
        )


async def acknowledge(identity, ctx, base, result):
    """Reconcile a lost POST response by finding our durable comment marker."""
    from a2a_server.forgejo_webhooks import (
        _comment,
        _is_self_authored,
        forgejo_json,
    )

    marker = f'<!-- codetether-inbox:{identity} -->'
    owner, name = ctx['repo'].split('/', 1)
    path = (
        f'/repos/{quote(owner, safe="")}/{quote(name, safe="")}'
        f'/issues/{ctx["number"]}/comments'
    )
    page = 1
    while True:
        comments = await forgejo_json(
            'GET', base, f'{path}?limit=100&page={page}'
        )
        if not isinstance(comments, list):
            raise RuntimeError('forgejo_invalid_comments_response')
        if any(
            marker in str(comment.get('body') or '')
            and _is_self_authored({'comment': comment}, 'issue_comment')
            for comment in comments
        ):
            return
        if len(comments) < COMMENT_PAGE_SIZE:
            break
        page += 1
    if result.get('accepted'):
        task = result.get('forgejo_agent_task_url')
        body = '## 🛠️ CodeTether Fix\n\nYour request is queued durably.'
        if task:
            body = '## 🛠️ CodeTether Fix\n\nYour request has a durable task handoff.'
            terminal = result.get('existing_task_status')
            if terminal in {'completed', 'failed', 'cancelled'}:
                body = f'## 🛠️ CodeTether Fix\n\nThis request already has a {terminal} task; it was not restarted.'
            body += f'\n\n[Track the task]({task})'
    else:
        body = (
            '## 🤖 CodeTether\n\nAsk me explicitly to fix, implement, handle, '
            'or update code, for example: `@codetether handle this issue`.'
        )
    await _comment(base, ctx['repo'], ctx['number'], f'{body}\n\n{marker}')
