"""
Knative CloudEvents Publisher for A2A Server Task Routing.

This module publishes CloudEvents to a Knative Broker for event-driven task
distribution. Tasks are published as structured CloudEvents that can be
consumed by Knative Triggers for routing to appropriate workers.

Architecture:
- Tasks are published to Knative Broker as CloudEvents
- Knative Triggers filter and route events to worker services
- Workers consume events via HTTP sink or subscription

Configuration:
- KNATIVE_BROKER_URL: Broker ingress URL (default: cluster-local broker)
- KNATIVE_ENABLED: Enable/disable CloudEvents publishing (default: false)
- KNATIVE_RETRY_MAX: Maximum retry attempts (default: 3)
- KNATIVE_RETRY_DELAY: Initial retry delay in seconds (default: 1.0)

CloudEvent Types:
- codetether.task.created: New task created for processing
- codetether.task.updated: Task status updated
- codetether.session.created: New session started
- codetether.session.message: Message in session
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

import aiohttp

logger = logging.getLogger(__name__)

# Default Knative Broker URL (cluster-local)
DEFAULT_BROKER_URL = (
    'http://broker-ingress.knative-eventing.svc.cluster.local'
    '/a2a-server/task-broker'
)

# Configuration from environment
KNATIVE_BROKER_URL = os.environ.get('KNATIVE_BROKER_URL', DEFAULT_BROKER_URL)
KNATIVE_ENABLED = os.environ.get('KNATIVE_ENABLED', 'false').lower() in (
    'true',
    '1',
    'yes',
)
KNATIVE_RETRY_MAX = int(os.environ.get('KNATIVE_RETRY_MAX', '3'))
KNATIVE_RETRY_DELAY = float(os.environ.get('KNATIVE_RETRY_DELAY', '1.0'))
KNATIVE_TIMEOUT = float(os.environ.get('KNATIVE_TIMEOUT', '10.0'))

# CloudEvent source identifier
CE_SOURCE = os.environ.get('KNATIVE_CE_SOURCE', 'a2a-server')


class KnativeEventError(Exception):
    """Raised when CloudEvent publishing fails."""

    pass


class BrokerUnavailableError(KnativeEventError):
    """Raised when the Knative Broker is unavailable."""

    pass


class EventPublishTimeoutError(KnativeEventError):
    """Raised when event publishing times out."""

    pass


def get_broker_url() -> str:
    """
    Get the Knative Broker ingress URL.

    Returns:
        The configured broker URL or default cluster-local URL.
    """
    return KNATIVE_BROKER_URL


def is_enabled() -> bool:
    """
    Check if Knative event publishing is enabled.

    Returns:
        True if KNATIVE_ENABLED is set to true/1/yes.
    """
    return KNATIVE_ENABLED


def _build_cloudevent_headers(
    event_type: str,
    session_id: str,
    event_id: Optional[str] = None,
    extensions: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """
    Build CloudEvent HTTP headers.

    Args:
        event_type: The CloudEvent type (e.g., 'codetether.task.created')
        session_id: Session ID for event correlation
        event_id: Optional event ID (generated if not provided)
        extensions: Optional CloudEvent extension attributes

    Returns:
        Dictionary of HTTP headers for CloudEvent.
    """
    now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    headers = {
        'ce-specversion': '1.0',
        'ce-type': event_type,
        'ce-source': CE_SOURCE,
        'ce-id': event_id or str(uuid4()),
        'ce-time': now,
        'ce-session': session_id,
        'Content-Type': 'application/json',
    }

    # Add extension attributes
    if extensions:
        for key, value in extensions.items():
            if value is not None:
                headers[f'ce-{key}'] = str(value)

    return headers


async def _publish_event_with_retry(
    session: aiohttp.ClientSession,
    url: str,
    headers: Dict[str, str],
    body: Dict[str, Any],
    max_retries: int = KNATIVE_RETRY_MAX,
    initial_delay: float = KNATIVE_RETRY_DELAY,
) -> bool:
    """
    Publish a CloudEvent with exponential backoff retry.

    Args:
        session: aiohttp client session
        url: Broker ingress URL
        headers: CloudEvent headers
        body: Event payload
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay between retries (doubles each retry)

    Returns:
        True if event was published successfully.

    Raises:
        BrokerUnavailableError: If broker is unreachable after all retries.
        EventPublishTimeoutError: If request times out.
        KnativeEventError: For other publishing errors.
    """
    delay = initial_delay
    last_error: Optional[Exception] = None

    for attempt in range(max_retries + 1):
        try:
            async with session.post(
                url,
                headers=headers,
                json=body,
                timeout=aiohttp.ClientTimeout(total=KNATIVE_TIMEOUT),
            ) as response:
                if response.status in (200, 201, 202, 204):
                    logger.debug(
                        f'CloudEvent published: type={headers.get("ce-type")} '
                        f'id={headers.get("ce-id")}'
                    )
                    return True

                # Handle specific HTTP errors
                if response.status == 404:
                    raise BrokerUnavailableError(
                        f'Broker not found at {url} (404)'
                    )
                elif response.status >= 500:
                    # Server error - retry
                    error_body = await response.text()
                    last_error = KnativeEventError(
                        f'Broker error {response.status}: {error_body}'
                    )
                    logger.warning(
                        f'Broker returned {response.status}, '
                        f'attempt {attempt + 1}/{max_retries + 1}'
                    )
                else:
                    # Client error - don't retry
                    error_body = await response.text()
                    raise KnativeEventError(
                        f'Event rejected with status {response.status}: '
                        f'{error_body}'
                    )

        except asyncio.TimeoutError:
            last_error = EventPublishTimeoutError(
                f'Timeout publishing event after {KNATIVE_TIMEOUT}s'
            )
            logger.warning(
                f'Timeout publishing event, '
                f'attempt {attempt + 1}/{max_retries + 1}'
            )

        except aiohttp.ClientConnectorError as e:
            last_error = BrokerUnavailableError(
                f'Cannot connect to broker at {url}: {e}'
            )
            logger.warning(
                f'Cannot connect to broker, '
                f'attempt {attempt + 1}/{max_retries + 1}: {e}'
            )

        except aiohttp.ClientError as e:
            last_error = KnativeEventError(f'HTTP client error: {e}')
            logger.warning(
                f'HTTP error publishing event, '
                f'attempt {attempt + 1}/{max_retries + 1}: {e}'
            )

        # Wait before retry (exponential backoff)
        if attempt < max_retries:
            await asyncio.sleep(delay)
            delay *= 2  # Exponential backoff

    # All retries exhausted
    raise last_error or KnativeEventError('Failed to publish event')


async def publish_task_event(
    session_id: str,
    task_id: str,
    prompt: str,
    agent: Optional[str] = None,
    model: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    tenant_id: Optional[str] = None,
    notify_email: Optional[str] = None,
) -> bool:
    """
    Publish a task.created CloudEvent to the Knative Broker.

    Args:
        session_id: Session ID for event correlation
        task_id: Unique task identifier
        prompt: Task prompt/instruction
        agent: Optional agent type (e.g., 'build', 'plan')
        model: Optional model specification (e.g., 'anthropic/claude-sonnet')
        metadata: Optional additional task metadata
        tenant_id: Optional tenant ID for multi-tenant routing
        notify_email: Optional email address for task completion notifications

    Returns:
        True if event was published successfully.

    Raises:
        BrokerUnavailableError: If broker is unreachable.
        EventPublishTimeoutError: If request times out.
        KnativeEventError: For other errors.

    Note:
        If KNATIVE_ENABLED is false, this function returns True immediately
        without publishing (no-op mode for local development).
    """
    if not KNATIVE_ENABLED:
        logger.debug(
            f'Knative disabled, skipping task event: task_id={task_id}'
        )
        return True

    # Build extensions dict with only non-None values
    extensions: Dict[str, str] = {
        'taskid': task_id,
    }
    if agent:
        extensions['agent'] = agent
    if model:
        extensions['model'] = model
    if tenant_id:
        extensions['tenant'] = tenant_id

    headers = _build_cloudevent_headers(
        event_type='codetether.task.created',
        session_id=session_id,
        extensions=extensions,
    )

    body: Dict[str, Any] = {
        'task_id': task_id,
        'session_id': session_id,
        'prompt': prompt,
        'agent': agent,
        'model': model,
        'metadata': metadata or {},
    }

    # Add tenant and notification info if provided
    if tenant_id:
        body['tenant_id'] = tenant_id
    if notify_email:
        body['notify_email'] = notify_email

    async with aiohttp.ClientSession() as session:
        return await _publish_event_with_retry(
            session=session,
            url=KNATIVE_BROKER_URL,
            headers=headers,
            body=body,
        )


async def publish_session_event(
    session_id: str,
    event_type: str,
    data: Dict[str, Any],
) -> bool:
    """
    Publish a generic session CloudEvent to the Knative Broker.

    Args:
        session_id: Session ID for event correlation
        event_type: Event type suffix (will be prefixed with 'codetether.')
        data: Event payload data

    Returns:
        True if event was published successfully.

    Raises:
        BrokerUnavailableError: If broker is unreachable.
        EventPublishTimeoutError: If request times out.
        KnativeEventError: For other errors.

    Note:
        If KNATIVE_ENABLED is false, this function returns True immediately
        without publishing (no-op mode for local development).
    """
    if not KNATIVE_ENABLED:
        logger.debug(
            f'Knative disabled, skipping session event: '
            f'type={event_type}, session={session_id}'
        )
        return True

    # Ensure event type has proper prefix
    full_event_type = (
        event_type
        if event_type.startswith('codetether.')
        else f'codetether.{event_type}'
    )

    headers = _build_cloudevent_headers(
        event_type=full_event_type,
        session_id=session_id,
    )

    body = {
        'session_id': session_id,
        **data,
    }

    async with aiohttp.ClientSession() as session:
        return await _publish_event_with_retry(
            session=session,
            url=KNATIVE_BROKER_URL,
            headers=headers,
            body=body,
        )


async def publish_task_status_event(
    session_id: str,
    task_id: str,
    status: str,
    result: Optional[str] = None,
    error: Optional[str] = None,
    worker_id: Optional[str] = None,
) -> bool:
    """
    Publish a task.updated CloudEvent when task status changes.

    Args:
        session_id: Session ID for event correlation
        task_id: Task identifier
        status: New task status (pending, running, completed, failed, cancelled)
        result: Optional task result (for completed tasks)
        error: Optional error message (for failed tasks)
        worker_id: Optional ID of worker that processed the task

    Returns:
        True if event was published successfully.

    Note:
        If KNATIVE_ENABLED is false, this function returns True immediately.
    """
    if not KNATIVE_ENABLED:
        logger.debug(
            f'Knative disabled, skipping task status event: '
            f'task_id={task_id}, status={status}'
        )
        return True

    headers = _build_cloudevent_headers(
        event_type='codetether.task.updated',
        session_id=session_id,
        extensions={
            'taskid': task_id,
            'taskstatus': status,
            'workerid': worker_id,
        },
    )

    body = {
        'task_id': task_id,
        'session_id': session_id,
        'status': status,
        'result': result,
        'error': error,
        'worker_id': worker_id,
    }

    async with aiohttp.ClientSession() as session:
        return await _publish_event_with_retry(
            session=session,
            url=KNATIVE_BROKER_URL,
            headers=headers,
            body=body,
        )


# Convenience function for health checks
async def check_broker_health() -> Dict[str, Any]:
    """
    Check if the Knative Broker is reachable.

    Returns:
        Dictionary with health status:
        - enabled: Whether Knative publishing is enabled
        - healthy: Whether broker is reachable (only if enabled)
        - broker_url: Configured broker URL
        - error: Error message if unhealthy
    """
    result = {
        'enabled': KNATIVE_ENABLED,
        'broker_url': KNATIVE_BROKER_URL,
        'healthy': False,
        'error': None,
    }

    if not KNATIVE_ENABLED:
        result['healthy'] = True  # Not enabled = no health check needed
        return result

    try:
        async with aiohttp.ClientSession() as session:
            # Send OPTIONS request to check connectivity
            async with session.options(
                KNATIVE_BROKER_URL,
                timeout=aiohttp.ClientTimeout(total=5.0),
            ) as response:
                # Broker should respond (even with 405 Method Not Allowed)
                result['healthy'] = response.status < 500
                if not result['healthy']:
                    result['error'] = (
                        f'Broker returned status {response.status}'
                    )

    except asyncio.TimeoutError:
        result['error'] = 'Timeout connecting to broker'
    except aiohttp.ClientConnectorError as e:
        result['error'] = f'Cannot connect to broker: {e}'
    except Exception as e:
        result['error'] = f'Unexpected error: {e}'

    return result
