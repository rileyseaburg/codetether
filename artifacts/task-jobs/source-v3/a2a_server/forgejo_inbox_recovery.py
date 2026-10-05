"""Recover a named legacy delivery through normal durable intake, never direct work.

Example (read-only by default)::

    python -m a2a_server.forgejo_inbox_recovery \
        'riley/spotlessbinco#5863:issues:body'

Add ``--enqueue`` only after reviewing the printed eligibility. Existing tasks,
closed issues, missing mentions and self-authored events require manual review.
"""
# Reuse canonical private parsing helpers; explicit safety gates fail closed.
# ruff: noqa: E501, SLF001

import argparse
import asyncio
import json

from urllib.parse import quote

from a2a_server import forgejo_inbox as inbox
from a2a_server import forgejo_webhooks as hooks
from a2a_server.github_app.mention import is_fix_request


async def recover(key, *, enqueue=False):  # noqa: PLR0911 (explicit eligibility gates)
    """Rehydrate one orphan from provider truth; leave the legacy audit row intact."""
    db = await inbox.pool()
    async with db.acquire() as conn:
        legacy = await conn.fetchrow(
            """
            SELECT repo, issue_number, event FROM forgejo_webhook_deliveries
            WHERE delivery_key = $1
        """,
            key,
        )
        if legacy is None:
            return {'eligible': False, 'reason': 'legacy-delivery-not-found'}
        repo, number = legacy['repo'], legacy['issue_number']
        existing = await conn.fetchval(
            """
            SELECT id FROM tasks WHERE metadata->>'source' = 'forgejo-webhook'
                AND metadata->>'repo' = $1 AND metadata->>'issue_number' = $2
            LIMIT 1
        """,
            repo,
            str(number),
        )
        if existing:
            return {
                'eligible': False,
                'reason': 'existing-work',
                'task_id': str(existing),
            }
    base = hooks._setting('FORGEJO_API_URL').rstrip('/')
    if not base:
        raise RuntimeError('FORGEJO_API_URL must be configured')
    owner, name = repo.split('/', 1)
    path = f'/repos/{quote(owner, safe="")}/{quote(name, safe="")}'
    native = await hooks.forgejo_json(
        'GET', base, f'{path}/agent/tasks?issue_index={number}&limit=1'
    )
    if not isinstance(native, dict) or not isinstance(
        native.get('tasks'), list
    ):
        return {'eligible': False, 'reason': 'native-task-state-unavailable'}
    if native['tasks'] or native.get('total_count', 0):
        return {'eligible': False, 'reason': 'existing-native-work'}
    issue = await hooks.forgejo_json('GET', base, f'{path}/issues/{number}')
    if issue.get('state') != 'open':
        return {'eligible': False, 'reason': 'issue-not-open'}
    repository = await hooks.forgejo_json('GET', base, path)
    event = legacy['event']
    payload = {'issue': issue, 'repository': repository, 'action': 'opened'}
    if ':comment:' in key:
        comment_id = int(key.rsplit(':', 1)[-1])
        comment = await hooks.forgejo_json(
            'GET', base, f'{path}/issues/comments/{comment_id}'
        )
        if str(comment.get('issue_url') or '').rstrip('/').rsplit('/', 1)[
            -1
        ] != str(number):
            return {'eligible': False, 'reason': 'comment-issue-mismatch'}
        payload.update(action='created', comment=comment)
    if hooks._is_self_authored(payload, event):
        return {'eligible': False, 'reason': 'self-authored-event'}
    ctx = hooks._context(event, payload)
    if not ctx or not is_fix_request(ctx['body']):
        return {'eligible': False, 'reason': 'no-current-actionable-mention'}
    if ctx['repo'] != repo or ctx['number'] != number:
        return {'eligible': False, 'reason': 'provider-identity-mismatch'}
    result = {
        'eligible': True,
        'delivery_key': key,
        'repo': repo,
        'issue_number': number,
    }
    if enqueue:
        result['receipt'] = await inbox.accept(event, ctx, base)
    return result


def main():
    """Expose an explicit, idempotent recovery operation with a dry-run default."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('delivery_key')
    parser.add_argument('--enqueue', action='store_true')
    args = parser.parse_args()
    print(
        json.dumps(
            asyncio.run(recover(args.delivery_key, enqueue=args.enqueue))
        )
    )


if __name__ == '__main__':
    main()
