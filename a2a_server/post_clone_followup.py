"""Queue follow-up work after repository preparation finishes."""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


async def enqueue_post_clone_followup(bridge, task_id: str) -> Optional[str]:
    task = await bridge.get_task(task_id)
    if task is None or task.agent_type != 'clone_repo':
        return None
    followup = (task.metadata or {}).get('post_clone_task')
    if not isinstance(followup, dict):
        return None
    queued = await bridge.create_task(
        codebase_id=task.codebase_id,
        title=followup.get('title') or 'Continue after clone',
        prompt=followup.get('prompt') or '',
        agent_type=followup.get('agent_type') or 'build',
        metadata=followup.get('metadata'),
    )
    if queued is None:
        logger.warning('Failed to enqueue post-clone follow-up for task %s', task_id)
        return None
    logger.info('Queued post-clone follow-up %s for task %s', queued.id, task_id)
    return queued.id
