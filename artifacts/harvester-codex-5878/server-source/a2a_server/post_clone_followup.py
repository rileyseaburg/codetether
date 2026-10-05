"""Post clone task follow-up helpers."""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


async def enqueue_post_clone_followup(bridge, task_id: str) -> Optional[str]:
    task = await bridge.get_task(task_id)
    if task is None or task.agent_type != 'clone_repo':
        return None
    metadata = task.metadata or {}
    if metadata.get('source') == 'github-app':
        logger.debug(
            'Skipping generic post-clone follow-up for GitHub App task %s',
            task_id,
        )
        return None
    followup = metadata.get('post_clone_task')
    if not isinstance(followup, dict):
        return None
    if metadata.get('source') == 'forgejo-webhook':
        from .persistent_worker_pool import create_and_dispatch_task

        followup_metadata = followup.get('metadata') or {}
        queued_id = await create_and_dispatch_task(
            workspace_id=task.codebase_id,
            title=followup.get('title') or 'Continue after clone',
            prompt=followup.get('prompt') or '',
            agent_type=followup.get('agent_type') or 'build',
            priority=int(followup.get('priority') or 0),
            metadata=followup_metadata,
            model_ref=followup.get('model_ref'),
            task_timeout_seconds=604800,
            github_issue_url=followup_metadata.get('forgejo_issue_url'),
        )
        forgejo_task_id = int(
            followup_metadata.get('forgejo_agent_task_id') or 0
        )
        if forgejo_task_id:
            from .forgejo_agent_client import update_task

            await update_task(
                repo=str(followup_metadata.get('repo') or ''),
                task_id=forgejo_task_id,
                base_url=str(followup_metadata.get('forgejo_api_url') or ''),
                status='running',
                external_task_id=str(queued_id),
            )
        return queued_id

    queued = await bridge.create_task(
        codebase_id=task.codebase_id,
        title=followup.get('title') or 'Continue after clone',
        prompt=followup.get('prompt') or '',
        agent_type=followup.get('agent_type') or 'build',
        priority=int(followup.get('priority') or metadata.get('priority') or 0),
        metadata=followup.get('metadata'),
        model_ref=followup.get('model_ref'),
    )
    if queued is None:
        logger.warning(
            'Failed to enqueue post-clone follow-up for task %s', task_id
        )
        return None
    logger.info(
        'Enqueued post-clone follow-up task %s after clone task %s',
        queued.id,
        task_id,
    )
    return queued.id
