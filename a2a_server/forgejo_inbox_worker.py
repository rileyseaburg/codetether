"""Restart-safe inbox pump; API acknowledgement never depends on its lifetime."""
# SQL readability and a process-owned lifecycle task match the server pattern.
# ruff: noqa: E501, PLW0603

import asyncio
import contextlib
import json
import logging

from a2a_server import forgejo_inbox as inbox
from a2a_server import forgejo_inbox_dispatch as effects
from a2a_server.github_app.mention import is_fix_request


logger = logging.getLogger(__name__)
_task = None


async def _advance(conn, row) -> None:
    """Checkpoint handoff before acknowledgement so ack failure cannot requeue work."""
    identity = row['delivery_id']
    ctx, base = inbox.decode(row['context']), row['api_base']
    ctx['_inbox_id'] = identity
    ctx['_native_task_id'] = row['native_task_id']
    plan, result = inbox.decode(row['plan']), inbox.decode(row['result'])
    if not row['receipt_notified']:
        await effects.acknowledge(
            identity + '-receipt',
            ctx,
            base,
            {'accepted': is_fix_request(ctx['body'])},
        )
        await conn.execute(
            """
            UPDATE forgejo_webhook_inbox SET receipt_notified = TRUE,
                updated_at = now() WHERE delivery_id = $1
        """,
            identity,
        )
    if result is None:
        await effects.ensure_issue_idle(conn, row, ctx, base)
        if plan is None and is_fix_request(ctx['body']):
            plan = await effects.prepare_plan(ctx, base)
            await conn.execute(
                """
                UPDATE forgejo_webhook_inbox SET plan = $2::jsonb, updated_at = now()
                WHERE delivery_id = $1
            """,
                identity,
                json.dumps(plan),
            )
        result = await effects.dispatch(ctx, base, plan)
        await conn.execute(
            """
            UPDATE forgejo_webhook_inbox SET result = $2::jsonb,
                state = 'dispatched', error_code = NULL, updated_at = now()
            WHERE delivery_id = $1
        """,
            identity,
            json.dumps(result),
        )
    if result.get('accepted'):
        await effects.acknowledge(identity, ctx, base, result)
    await conn.execute(
        """
        UPDATE forgejo_webhook_inbox SET state = 'acknowledged',
            error_code = NULL, updated_at = now() WHERE delivery_id = $1
    """,
        identity,
    )


async def process(identity):
    """Serialize one delivery across replicas, retrying with bounded backoff."""
    async with inbox.locked_delivery(identity) as conn:
        if conn is None:
            return
        row = await conn.fetchrow(
            """
            UPDATE forgejo_webhook_inbox SET attempts = attempts + 1,
                updated_at = now()
            WHERE delivery_id = $1 AND state != 'acknowledged'
                AND next_attempt_at <= now()
            RETURNING *
        """,
            identity,
        )
        if row is None:
            return
        try:
            async with asyncio.timeout(120):
                await _advance(conn, row)
        except (Exception, asyncio.CancelledError) as error:
            # Never persist provider response bodies, credentials or prompts as
            # diagnostics. The owning runtime logs the specific service failure.
            code = type(error).__name__
            status = getattr(error, 'status_code', None)
            if isinstance(status, int):
                code += f':{status}'
            try:
                await conn.execute(
                    """
                    UPDATE forgejo_webhook_inbox SET error_code = $2,
                        next_attempt_at = now() + make_interval(secs =>
                            LEAST(300, power(2, LEAST(attempts, 8))::int)),
                        updated_at = now() WHERE delivery_id = $1
                """,
                    identity,
                    code,
                )
            except Exception:
                logger.error(
                    'Inbox retry checkpoint unavailable delivery=%s', identity
                )
            logger.warning(
                'Forgejo intake pending delivery=%s error=%s', identity, code
            )
            if isinstance(error, asyncio.CancelledError):
                raise


async def reconcile():
    """Drain bounded work; one broken delivery does not starve unrelated work."""
    for row in await inbox.due_deliveries():
        try:
            await process(row['delivery_id'])
        except Exception as error:
            logger.warning(
                'Inbox processing unavailable error=%s', type(error).__name__
            )


def start():
    """Start the independently supervised pump, not a per-request background task."""
    global _task
    if _task is not None and not _task.done():
        return

    async def run() -> None:
        while True:
            try:
                await reconcile()
            except Exception as error:
                logger.warning(
                    'Forgejo inbox unavailable error=%s', type(error).__name__
                )
            await asyncio.sleep(5)

    _task = asyncio.create_task(run(), name='forgejo-inbox')


async def stop():
    """Cancel the pump without losing its durable pending receipts."""
    global _task
    if _task is None:
        return
    _task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await _task
    _task = None
