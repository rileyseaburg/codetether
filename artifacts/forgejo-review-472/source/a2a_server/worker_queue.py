"""Bounded enqueue helper for worker SSE event queues.

Caps the per-connection asyncio.Queue so a flooding producer cannot grow server
memory without bound. Uses non-blocking put with a drop-on-full policy: blocking
while holding the registry lock would deadlock, and sequenced (Class B) events
remain recoverable from the replay ring on reconnect, so a dropped live event is
not data loss. See codetether-agent/docs/transport-first-class-plan.md Phase 2.
"""

import asyncio
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

# Max buffered events per connected worker before drop-on-full kicks in.
WORKER_QUEUE_MAXSIZE = 1024


def make_worker_queue() -> 'asyncio.Queue':
    """Create a bounded queue for a worker SSE connection."""
    return asyncio.Queue(maxsize=WORKER_QUEUE_MAXSIZE)


def try_enqueue(queue: 'asyncio.Queue', event: Dict[str, Any], worker_id: str) -> bool:
    """Enqueue without blocking; drop and warn when the queue is full.

    Returns True when queued, False when dropped due to backpressure.
    """
    try:
        queue.put_nowait(event)
        return True
    except asyncio.QueueFull:
        logger.warning(
            'Worker %s queue full (max=%d); dropping %s event (recoverable '
            'via replay ring on reconnect)',
            worker_id,
            WORKER_QUEUE_MAXSIZE,
            event.get('event', 'message'),
        )
        return False
