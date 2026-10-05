"""Dedicated Temporal worker process for Forgejo agent workflows."""

from __future__ import annotations

import asyncio
import logging

from temporalio.worker import Worker

from .activities import (
    cancel_task,
    dispatch_fix,
    dispatch_review,
    dispatch_stage,
    finalize_workflow,
    publish_review,
)
from .config import get_temporal_client, temporal_settings
from .workflows import ForgejoAgentWorkflow

logger = logging.getLogger(__name__)


async def run_worker() -> None:
    settings = temporal_settings()
    if not settings.enabled:
        raise RuntimeError(
            'FORGEJO_TEMPORAL_ENABLED must be true for the worker'
        )
    client = await get_temporal_client()
    worker = Worker(
        client,
        task_queue=settings.task_queue,
        workflows=[ForgejoAgentWorkflow],
        activities=[
            dispatch_stage,
            dispatch_review,
            publish_review,
            dispatch_fix,
            cancel_task,
            finalize_workflow,
        ],
    )
    logger.info(
        'Starting Forgejo Temporal worker namespace=%s queue=%s',
        settings.namespace,
        settings.task_queue,
    )
    await worker.run()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_worker())


if __name__ == '__main__':
    main()
