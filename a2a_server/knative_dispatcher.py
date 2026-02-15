"""
Knative Eventing integration for task dispatch.

This module provides CloudEvent publishing to Knative Broker for
asynchronous task processing by worker services.
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.parse import urljoin

import aiohttp

logger = logging.getLogger(__name__)

# Knative Broker URL (set via env var or use default in-cluster address)
# Default uses the task-broker in a2a-server namespace (from knative-codetether-agent.yaml)
KNATIVE_BROKER_URL = os.environ.get(
    "KNATIVE_BROKER_URL",
    "http://broker-ingress.knative-eventing.svc.cluster.local/a2a-server/task-broker"
)

# Whether to enable Knative dispatch (can be disabled for local dev)
KNATIVE_ENABLED = os.environ.get("KNATIVE_DISPATCH_ENABLED", "true").lower() == "true"


class CloudEventPublisher:
    """Publisher for CloudEvents to Knative Broker."""

    def __init__(self, broker_url: Optional[str] = None):
        self.broker_url = broker_url or KNATIVE_BROKER_URL
        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                headers={
                    "Content-Type": "application/cloudevents+json",
                    "Ce-Specversion": "1.0",
                    "Ce-Id": "",  # Will be set per event
                    "Ce-Type": "",  # Will be set per event
                    "Ce-Source": "codetether:a2a-server",
                }
            )
        return self.session

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def publish(
        self,
        event_type: str,
        data: Dict[str, Any],
        event_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Publish a CloudEvent to the Knative Broker.

        Args:
            event_type: CloudEvent type (e.g., 'codetether.task.created')
            data: Event data payload
            event_id: Optional event ID (generated if not provided)

        Returns:
            Event ID if successful, None otherwise
        """
        if not KNATIVE_ENABLED:
            logger.debug(f"Knative dispatch disabled, skipping event: {event_type}")
            return None

        import uuid

        event_id = event_id or str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()

        ce_payload = {
            "id": event_id,
            "source": "codetether:a2a-server",
            "type": event_type,
            "time": timestamp,
            "specversion": "1.0",
            "data": data,
        }

        try:
            session = await self._get_session()
            async with session.post(self.broker_url, json=ce_payload) as resp:
                if resp.status >= 200 and resp.status < 300:
                    logger.info(
                        f"Published CloudEvent {event_id} (type={event_type}) to {self.broker_url}"
                    )
                    return event_id
                else:
                    body = await resp.text()
                    logger.error(
                        f"Failed to publish CloudEvent: status={resp.status}, body={body}"
                    )
                    return None
        except Exception as e:
            logger.error(f"Error publishing CloudEvent: {e}")
            return None


# Global publisher instance
_publisher: Optional[CloudEventPublisher] = None


async def get_publisher() -> CloudEventPublisher:
    """Get or create the global CloudEvent publisher."""
    global _publisher
    if _publisher is None:
        _publisher = CloudEventPublisher()
    return _publisher


async def close_publisher():
    """Close the global publisher."""
    global _publisher
    if _publisher:
        await _publisher.close()
        _publisher = None


async def dispatch_task_to_knative(
    task_id: str,
    title: str,
    description: str,
    agent_type: str = "build",
    model: Optional[str] = None,
    priority: int = 0,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """
    Dispatch a task to Knative for processing by a worker.

    This creates the task in the database AND publishes a CloudEvent
    to trigger a Knative worker in a single call.

    Args:
        task_id: Unique task identifier
        title: Task title
        description: Task prompt/description
        agent_type: Type of agent (build, plan, etc.)
        model: Model to use
        priority: Task priority
        metadata: Additional metadata

    Returns:
        CloudEvent ID if successful, None otherwise
    """
    import uuid

    event_id = str(uuid.uuid4())
    event_data = {
        "task_id": task_id,
        "title": title,
        "description": description,
        "agent_type": agent_type,
        "model": model,
        "priority": priority,
        "metadata": metadata or {},
        "dispatched_at": datetime.now(timezone.utc).isoformat(),
    }

    publisher = await get_publisher()
    return await publisher.publish(
        event_type="codetether.task.created",
        data=event_data,
        event_id=event_id,
    )


__all__ = [
    "CloudEventPublisher",
    "get_publisher",
    "close_publisher",
    "dispatch_task_to_knative",
    "KNATIVE_ENABLED",
    "KNATIVE_BROKER_URL",
]
