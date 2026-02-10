"""
Production HTTP Client — shared httpx client with connection pooling,
circuit breaker, exponential backoff, and structured logging.

Replaces scattered `async with httpx.AsyncClient() as client:` calls
that create/destroy TCP connections on every request.

Circuit Breaker States:
- CLOSED: Normal operation, requests flow through
- OPEN: Too many failures, requests fail immediately (fast fail)
- HALF_OPEN: After cooldown, allow one probe request through

Usage:
    from .http_client import get_http_client, http_request

    # Simple: uses shared client + circuit breaker automatically
    resp = await http_request('GET', '/api/optimization/report')

    # Direct client access
    client = get_http_client()
    resp = await client.get(...)
"""

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from enum import Enum
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

# -------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------

MARKETING_SITE_URL = os.environ.get('MARKETING_SITE_URL', 'http://localhost:3000')
MARKETING_API_KEY = os.environ.get('MARKETING_API_KEY', '')

# Connection pool settings
MAX_CONNECTIONS = int(os.environ.get('HTTP_MAX_CONNECTIONS', '20'))
MAX_KEEPALIVE = int(os.environ.get('HTTP_MAX_KEEPALIVE', '10'))

# Circuit breaker settings
CB_FAILURE_THRESHOLD = int(os.environ.get('CB_FAILURE_THRESHOLD', '5'))
CB_RECOVERY_TIMEOUT = int(os.environ.get('CB_RECOVERY_TIMEOUT_SECONDS', '60'))
CB_HALF_OPEN_MAX = int(os.environ.get('CB_HALF_OPEN_MAX_REQUESTS', '1'))

# Retry settings
RETRY_MAX_ATTEMPTS = int(os.environ.get('HTTP_RETRY_MAX_ATTEMPTS', '3'))
RETRY_BASE_DELAY = float(os.environ.get('HTTP_RETRY_BASE_DELAY_SECONDS', '1.0'))
RETRY_MAX_DELAY = float(os.environ.get('HTTP_RETRY_MAX_DELAY_SECONDS', '30.0'))
RETRY_BACKOFF_FACTOR = float(os.environ.get('HTTP_RETRY_BACKOFF_FACTOR', '2.0'))


# -------------------------------------------------------------------
# Circuit Breaker
# -------------------------------------------------------------------

class CircuitState(Enum):
    CLOSED = 'closed'
    OPEN = 'open'
    HALF_OPEN = 'half_open'


class CircuitBreaker:
    """
    Circuit breaker for external HTTP calls.

    Prevents cascading failures by failing fast when the target is unhealthy,
    then periodically probing to check recovery.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = CB_FAILURE_THRESHOLD,
        recovery_timeout: float = CB_RECOVERY_TIMEOUT,
        half_open_max: int = CB_HALF_OPEN_MAX,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max = half_open_max

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float = 0
        self._half_open_calls = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if time.monotonic() - self._last_failure_time >= self.recovery_timeout:
                return CircuitState.HALF_OPEN
        return self._state

    async def allow_request(self) -> bool:
        """Check if a request should be allowed through."""
        async with self._lock:
            current = self.state

            if current == CircuitState.CLOSED:
                return True
            elif current == CircuitState.HALF_OPEN:
                if self._half_open_calls < self.half_open_max:
                    self._half_open_calls += 1
                    return True
                return False
            else:  # OPEN
                return False

    async def record_success(self) -> None:
        """Record a successful request."""
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN or self.state == CircuitState.HALF_OPEN:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                self._half_open_calls = 0
                logger.info('Circuit breaker [%s]: CLOSED (recovered)', self.name)
            self._success_count += 1

    async def record_failure(self) -> None:
        """Record a failed request."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()

            if self._state == CircuitState.HALF_OPEN or self.state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                self._half_open_calls = 0
                logger.warning(
                    'Circuit breaker [%s]: OPEN (half-open probe failed, '
                    'will retry in %ds)',
                    self.name, self.recovery_timeout,
                )
            elif self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(
                    'Circuit breaker [%s]: OPEN (%d consecutive failures, '
                    'will retry in %ds)',
                    self.name, self._failure_count, self.recovery_timeout,
                )

    def get_health(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'state': self.state.value,
            'failure_count': self._failure_count,
            'success_count': self._success_count,
            'failure_threshold': self.failure_threshold,
            'recovery_timeout_seconds': self.recovery_timeout,
        }


# -------------------------------------------------------------------
# Shared Client Manager
# -------------------------------------------------------------------

class HttpClientManager:
    """
    Manages a shared httpx.AsyncClient with connection pooling
    and circuit breaker integration.
    """

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None
        self._circuit = CircuitBreaker('marketing_site')
        self._started = False

    async def start(self) -> None:
        """Initialize the shared HTTP client with connection pool."""
        if self._started:
            return

        limits = httpx.Limits(
            max_connections=MAX_CONNECTIONS,
            max_keepalive_connections=MAX_KEEPALIVE,
        )

        headers = {'Content-Type': 'application/json'}
        if MARKETING_API_KEY:
            headers['x-api-key'] = MARKETING_API_KEY

        self._client = httpx.AsyncClient(
            base_url=MARKETING_SITE_URL,
            headers=headers,
            limits=limits,
            timeout=httpx.Timeout(30.0, connect=10.0),
        )
        self._started = True
        logger.info(
            'HTTP client started (base_url=%s, max_conn=%d)',
            MARKETING_SITE_URL, MAX_CONNECTIONS,
        )

    async def stop(self) -> None:
        """Gracefully close the shared HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
        self._started = False
        logger.info('HTTP client stopped')

    @property
    def client(self) -> httpx.AsyncClient:
        if not self._client:
            raise RuntimeError(
                'HTTP client not started. Call start() first or use '
                'http_request() which handles lifecycle automatically.'
            )
        return self._client

    @property
    def circuit(self) -> CircuitBreaker:
        return self._circuit

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: Optional[Any] = None,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        retries: int = RETRY_MAX_ATTEMPTS,
        skip_circuit_breaker: bool = False,
    ) -> httpx.Response:
        """
        Make an HTTP request with circuit breaker and exponential backoff.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: URL path (relative to base_url)
            json: JSON body
            params: Query parameters
            timeout: Override timeout for this request
            retries: Max retry attempts (0 = no retries)
            skip_circuit_breaker: Bypass circuit breaker (for health probes)

        Returns:
            httpx.Response

        Raises:
            CircuitBreakerOpenError: Circuit breaker is open
            httpx.RequestError: After all retries exhausted
        """
        if not skip_circuit_breaker:
            if not await self._circuit.allow_request():
                raise CircuitBreakerOpenError(
                    f'Circuit breaker [{self._circuit.name}] is open '
                    f'(state={self._circuit.state.value})'
                )

        last_error: Optional[Exception] = None
        attempt = 0

        while attempt <= retries:
            try:
                kwargs: Dict[str, Any] = {}
                if json is not None:
                    kwargs['json'] = json
                if params is not None:
                    kwargs['params'] = params
                if timeout is not None:
                    kwargs['timeout'] = timeout

                resp = await self.client.request(method, path, **kwargs)

                # 5xx = server error, eligible for retry
                if resp.status_code >= 500 and attempt < retries:
                    logger.warning(
                        'HTTP %s %s: %d (attempt %d/%d, retrying)',
                        method, path, resp.status_code, attempt + 1, retries + 1,
                    )
                    last_error = httpx.HTTPStatusError(
                        f'{resp.status_code}', request=resp.request, response=resp,
                    )
                    attempt += 1
                    await self._backoff_sleep(attempt)
                    continue

                # Success or client error (no retry)
                if not skip_circuit_breaker:
                    if resp.status_code < 500:
                        await self._circuit.record_success()
                    else:
                        await self._circuit.record_failure()

                return resp

            except httpx.RequestError as e:
                last_error = e
                if not skip_circuit_breaker:
                    await self._circuit.record_failure()

                if attempt < retries:
                    logger.warning(
                        'HTTP %s %s: %s (attempt %d/%d, retrying)',
                        method, path, type(e).__name__, attempt + 1, retries + 1,
                    )
                    attempt += 1
                    await self._backoff_sleep(attempt)
                    continue
                break

        # All retries exhausted
        logger.error(
            'HTTP %s %s: all %d attempts failed: %s',
            method, path, retries + 1, last_error,
        )
        raise last_error  # type: ignore[misc]

    async def _backoff_sleep(self, attempt: int) -> None:
        """Exponential backoff with jitter."""
        import random
        delay = min(
            RETRY_BASE_DELAY * (RETRY_BACKOFF_FACTOR ** (attempt - 1)),
            RETRY_MAX_DELAY,
        )
        jitter = delay * 0.2 * random.random()
        await asyncio.sleep(delay + jitter)

    def get_health(self) -> Dict[str, Any]:
        return {
            'started': self._started,
            'base_url': MARKETING_SITE_URL,
            'circuit_breaker': self._circuit.get_health(),
        }


class CircuitBreakerOpenError(Exception):
    """Raised when a request is blocked by an open circuit breaker."""
    pass


# -------------------------------------------------------------------
# Global Instance
# -------------------------------------------------------------------

_manager: Optional[HttpClientManager] = None


def get_http_client_manager() -> Optional[HttpClientManager]:
    return _manager


def get_http_client() -> httpx.AsyncClient:
    """Get the shared httpx client. Raises if not started."""
    if not _manager:
        raise RuntimeError('HTTP client manager not started')
    return _manager.client


async def start_http_client() -> HttpClientManager:
    global _manager
    if _manager is not None:
        return _manager
    _manager = HttpClientManager()
    await _manager.start()
    return _manager


async def stop_http_client() -> None:
    global _manager
    if _manager:
        await _manager.stop()
        _manager = None


# -------------------------------------------------------------------
# Convenience function
# -------------------------------------------------------------------

async def http_request(
    method: str,
    path: str,
    *,
    json: Optional[Any] = None,
    params: Optional[Dict[str, Any]] = None,
    timeout: Optional[float] = None,
    retries: int = RETRY_MAX_ATTEMPTS,
) -> httpx.Response:
    """
    Make an HTTP request to the marketing site with circuit breaker + retry.

    This is the primary entry point for all marketing-site API calls.
    """
    if not _manager:
        raise RuntimeError('HTTP client not started. Ensure start_http_client() is called on startup.')
    return await _manager.request(
        method, path, json=json, params=params, timeout=timeout, retries=retries,
    )
