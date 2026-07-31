"""Exactly-once handling of Forgejo webhook deliveries.

Forgejo can deliver the same event through more than one hook: a repository hook
and an instance-wide system hook both pointing at this endpoint. Both carry the
same `comment.id`, and they arrive milliseconds apart, so a read-then-act guard
loses the race and the bot answers the same mention twice.

`claim_delivery` performs an atomic insert. The first delivery to insert its key
wins and proceeds; every duplicate sees the conflict and stops. The claim is
keyed on the event's own identity (comment id, or issue number for an opened
issue), so a genuinely new mention is never suppressed.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping, Optional

logger = logging.getLogger(__name__)

_TABLE = 'forgejo_webhook_deliveries'

# Deliveries older than this may be pruned; the window only needs to outlive
# duplicate hook fan-out, which happens within milliseconds.
RETENTION_HOURS = 72


def delivery_key(event: str, ctx: Mapping[str, Any]) -> Optional[str]:
    """Return a stable identity for one logical webhook event.

    Returns:
        A key unique to the triggering comment or opened issue, or None when the
        event carries no usable identity.
    """
    repo = str(ctx.get('repo') or '').strip()
    number = ctx.get('number')
    if not repo or not number:
        return None

    comment_id = ctx.get('comment_id') or 0
    try:
        comment_id = int(comment_id)
    except (TypeError, ValueError):
        comment_id = 0

    if comment_id:
        return f'{repo}#{number}:comment:{comment_id}'
    # An opened issue has no comment yet; its body mention is a single event.
    return f'{repo}#{number}:{event}:body'


async def ensure_table(conn: Any) -> None:
    """Create the delivery-claim table when it does not already exist."""
    await conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {_TABLE} (
            delivery_key TEXT PRIMARY KEY,
            repo TEXT NOT NULL,
            issue_number INTEGER,
            event TEXT,
            claimed_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )


async def claim_delivery(
    event: str, ctx: Mapping[str, Any]
) -> tuple[bool, Optional[str]]:
    """Atomically claim one webhook delivery.

    Returns:
        `(claimed, key)`. `claimed` is True only for the delivery that won the
        race. When the database is unavailable the delivery is allowed through
        so a storage outage cannot silence the bot entirely.
    """
    key = delivery_key(event, ctx)
    if not key:
        return True, None

    from . import database as db

    try:
        pool = await db.get_pool()
        if not pool:
            return True, key
        async with pool.acquire() as conn:
            await ensure_table(conn)
            claimed = await conn.fetchval(
                f"""
                INSERT INTO {_TABLE}
                    (delivery_key, repo, issue_number, event)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (delivery_key) DO NOTHING
                RETURNING delivery_key
                """,
                key,
                str(ctx.get('repo') or ''),
                int(ctx.get('number') or 0),
                event,
            )
            if claimed is None:
                logger.info(
                    'Ignoring duplicate Forgejo delivery %s (already claimed)',
                    key,
                )
                return False, key
            await conn.execute(
                f"DELETE FROM {_TABLE} WHERE claimed_at < now() - interval"
                f" '{RETENTION_HOURS} hours'"
            )
    except Exception as exc:
        # Never lose real work because the claim store misbehaved.
        logger.warning('Delivery claim failed for %s: %s', key, exc)
        return True, key

    return True, key
