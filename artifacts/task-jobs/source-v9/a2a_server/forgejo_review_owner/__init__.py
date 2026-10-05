"""Single durable review owner for each Forgejo PR head."""

import hashlib
import os
import uuid


STATUS_CONTEXT = 'CodeTether / Harvester Review'


def enabled(repo):
    return repo in {
        r.strip()
        for r in os.getenv('FORGEJO_SINGLE_REVIEW_REPOS', '').split(',')
        if r.strip()
    }


def identities(repo, number, sha):
    key = f'forgejo-review-owner:{repo}:{number}:{sha}'
    return str(
        uuid.uuid5(uuid.NAMESPACE_URL, key)
    ), 'forgejo-review-' + hashlib.sha256(key.encode()).hexdigest()[:40]


async def ensure_review(repo, number, *, expected_sha=None):
    """Bind current state to one workflow; duplicate deliveries attach, not rerun."""
    from temporalio.common import (
        WorkflowIDConflictPolicy,
        WorkflowIDReusePolicy,
    )
    from temporalio.exceptions import WorkflowAlreadyStartedError

    from a2a_server.temporal.config import (
        get_temporal_client,
        temporal_settings,
    )

    from .state import current_pr, ensure_record
    from .workflow import HeadReviewWorkflow

    if not enabled(repo):
        raise RuntimeError('single_review_not_enabled')
    pr = await current_pr(repo, number)
    sha = pr['head']['sha']
    if expected_sha and sha != expected_sha:
        raise RuntimeError('review_head_advanced')
    task_id, workflow_id = identities(repo, number, sha)
    from .hooks import cancel_old_reviews

    await cancel_old_reviews(repo, number, sha)
    await ensure_record(repo, pr, task_id, workflow_id)
    client = await get_temporal_client()
    try:
        await client.start_workflow(
            HeadReviewWorkflow.run,
            {'repo': repo, 'pr': number, 'sha': sha, 'task_id': task_id},
            id=workflow_id,
            task_queue=temporal_settings().task_queue,
            id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
            id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
        )
    except WorkflowAlreadyStartedError:
        pass
    return task_id
