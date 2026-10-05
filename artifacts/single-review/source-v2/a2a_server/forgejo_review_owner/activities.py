"""Retry-safe activities for review capture, harvester execution and publication."""

import os

from temporalio import activity
from temporalio.exceptions import ApplicationError

from a2a_server import database as db
from a2a_server.temporal.activities import safe_activity

from . import evidence
from .state import bound_pr, checkpoint, finish, publish_state, save_snapshot
from .state import snapshot as load_snapshot


@activity.defn(name='forgejo_head_review_prepare')
@safe_activity('review_capture_failed')
async def prepare(arg):
    await bound_pr(arg)
    await db.db_update_task_status(
        arg['task_id'], 'working', result='', error=''
    )
    await publish_state(arg, 'pending', 'Complete diff review in progress')
    stored = await load_snapshot(arg['task_id'])
    target = os.getenv('FORGEJO_REVIEW_SAFE_WORKER', '').strip()
    if not target:
        raise ApplicationError('review_safe_worker_missing', non_retryable=True)
    if stored:
        context, chunks = stored['context'], stored['chunks']
        context = await evidence.refresh_context(arg, context)
    else:
        try:
            context, chunks = await evidence.capture(arg)
        except ValueError as error:
            reason = str(error)
            if reason not in {
                'review_diff_size_out_of_bounds',
                'review_chunk_capacity_exceeded',
                'review_coverage_mismatch',
            }:
                reason = 'review_diff_invalid'
            raise ApplicationError(
                reason, type=reason, non_retryable=True
            ) from None
    # Persist exact immutable input before dispatch; Temporal history contains only count/IDs.
    await save_snapshot(arg['task_id'], context, chunks)
    await checkpoint(
        arg['task_id'],
        {
            'review_attempt': arg.get('attempt', 1),
            'review_context': context,
            'review_manifest': [
                {k: c[k] for k in ('index', 'sha256', 'bytes')} for c in chunks
            ],
        },
    )
    return len(chunks)


@activity.defn(name='forgejo_head_review_chunk')
@safe_activity('review_chunk_dispatch_failed')
async def dispatch(arg):
    from a2a_server.persistent_worker_pool import create_and_dispatch_task

    await bound_pr(arg)
    stored = await load_snapshot(arg['task_id'])
    chunk = stored['chunks'][arg['index'] - 1]
    owner = await db.db_get_task(arg['task_id'])
    text = evidence.prompt(
        owner['metadata']['review_context'], chunk, len(stored['chunks'])
    )
    if len(text.encode()) > 240000:
        raise ApplicationError('review_prompt_too_large', non_retryable=True)
    key = f'forgejo-head-review:{arg["task_id"]}:{arg.get("attempt", 1)}:{chunk["index"]}:{chunk["sha256"]}'
    return await create_and_dispatch_task(
        workspace_id='global',
        title=f'PR #{arg["pr"]} review chunk {chunk["index"]}',
        prompt=text,
        agent_type='plan',
        model_ref=os.environ.get('GITHUB_APP_MODEL_REF'),
        task_timeout_seconds=1800,
        metadata={
            'source': 'forgejo-webhook',
            'workflow_stage': 'review_chunk',
            'forgejo_work_key': key,
            'repo': arg['repo'],
            'pr_number': arg['pr'],
            'pr_head_sha': arg['sha'],
            'review_owner_id': arg['task_id'],
            'review_chunk_sha256': chunk['sha256'],
            'target_agent_name': os.environ['FORGEJO_REVIEW_SAFE_WORKER'],
            'required_capabilities': ['review-readonly'],
            'max_steps': 4,
        },
    )


@activity.defn(name='forgejo_head_review_chunk_state')
@safe_activity('review_chunk_state_failed')
async def chunk_state(arg):
    await bound_pr(arg)
    task = await db.db_get_task(arg['chunk_task'])
    if not task:
        raise ApplicationError('review_chunk_missing', non_retryable=True)
    status = task['status']
    if status not in {'completed', 'failed', 'cancelled'}:
        return 'pending'
    if status != 'completed':
        return 'BLOCKED'
    meta = task['metadata']
    try:
        parsed = evidence.parse_result(
            str(task.get('result') or ''), meta['review_chunk_sha256']
        )
    except ValueError:
        return 'BLOCKED'
    await checkpoint(arg['chunk_task'], {'review_validated_output': parsed})
    return parsed['verdict']


@activity.defn(name='forgejo_head_review_finish')
@safe_activity('review_publication_failed')
async def complete(arg):
    owner = await db.db_get_task(arg['task_id'])
    manifest = owner['metadata'].get('review_manifest') or []
    ids = arg.get('chunks') or []
    if (
        arg.get('blocked')
        or len(ids) != len(manifest)
        or len(set(ids)) != len(ids)
        or not ids
    ):
        reason = arg.get('reason', 'review_coverage_or_execution_failed')
        if (
            not isinstance(reason, str)
            or not reason.startswith('review_')
            or len(reason) > 80
        ):
            reason = 'review_execution_failed'
        await checkpoint(
            arg['task_id'],
            {'review_error_reason': reason, 'review_chunk_task_ids': ids},
        )
        notes = []
        for task_id in ids[-2:]:
            task = await db.db_get_task(task_id)
            output = ((task or {}).get('metadata') or {}).get(
                'review_validated_output'
            ) or {}
            notes.append(
                f'Chunk task `{task_id}`: {str(output.get("summary") or "see task outcome")[:1500]}'
            )
        return await finish(
            arg,
            'BLOCKED',
            f'Review blocked: `{reason}`. No approval was issued.\n'
            + '\n'.join(notes),
        )
    outputs = []
    for index, task_id in enumerate(ids):
        task = await db.db_get_task(task_id)
        try:
            parsed = evidence.parse_result(
                str(task.get('result') or ''), manifest[index]['sha256']
            )
        except ValueError:
            parsed = None
        if (
            task['status'] != 'completed'
            or not parsed
            or parsed['reviewed_chunk_sha256'] != manifest[index]['sha256']
        ):
            return await finish(
                arg, 'BLOCKED', 'Exact chunk coverage was not established.'
            )
        outputs.append(parsed)
    verdict = (
        'BLOCKED'
        if any(o['verdict'] == 'BLOCKED' for o in outputs)
        else 'CHANGES_REQUESTED'
        if any(o['verdict'] == 'CHANGES_REQUESTED' for o in outputs)
        else 'APPROVED'
    )
    digest = owner['metadata']['review_context']['complete_diff_sha256']
    findings = [f for o in outputs for f in o['findings']]
    detail = f'Exact coverage: {len(ids)}/{len(manifest)} chunks; complete diff SHA-256 `{digest}`.\n'
    detail += '\n'.join(
        f'- {f["severity"]}: {f.get("file", "")} — {str(f.get("description", ""))[:2000]}'
        for f in findings
    )
    await checkpoint(
        arg['task_id'],
        {'review_chunk_task_ids': ids, 'review_findings': findings},
    )
    return await finish(arg, verdict, detail)


@activity.defn(name='forgejo_head_review_cancel')
@safe_activity('review_cancel_failed')
async def cancel(arg):
    from a2a_server.forgejo_agent_controls import _cancel_codetether_task

    for task_id in arg.get('chunks', []):
        task = await db.db_get_task(task_id)
        if task and task['status'] not in {'completed', 'failed', 'cancelled'}:
            await _cancel_codetether_task(task_id)
    if not arg.get('keep_owner'):
        await db.db_update_task_status(
            arg['task_id'], 'cancelled', error='review_cancelled_or_stale'
        )
    try:
        await publish_state(
            arg, 'error', 'Review cancelled; no approval issued'
        )
    except RuntimeError:
        pass


@activity.defn(name='forgejo_review_snapshot')
@safe_activity('review_snapshot_failed')
async def snapshot(task_id):
    task = await db.db_get_task(task_id)
    if not task:
        raise ApplicationError('review_record_missing', non_retryable=True)
    return {
        'status': task['status'],
        'verdict': (task.get('metadata') or {}).get('review_verdict', ''),
    }
