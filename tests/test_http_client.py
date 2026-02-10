"""
Tests for the shared HTTP client module.

Tests CircuitBreaker, HttpClientManager, connection pooling,
exponential backoff, and lifecycle management.
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from a2a_server.http_client import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitState,
    HttpClientManager,
    get_http_client,
    get_http_client_manager,
    start_http_client,
    stop_http_client,
    http_request,
)


# ============================================================================
# CircuitBreaker Tests
# ============================================================================


class TestCircuitBreaker:

    @pytest.mark.asyncio
    async def test_initial_state_closed(self):
        cb = CircuitBreaker('test')
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_allows_request_when_closed(self):
        cb = CircuitBreaker('test')
        assert await cb.allow_request() is True

    @pytest.mark.asyncio
    async def test_opens_after_threshold(self):
        cb = CircuitBreaker('test', failure_threshold=3)
        for _ in range(3):
            await cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert await cb.allow_request() is False

    @pytest.mark.asyncio
    async def test_does_not_open_below_threshold(self):
        cb = CircuitBreaker('test', failure_threshold=5)
        for _ in range(4):
            await cb.record_failure()
        assert cb.state == CircuitState.CLOSED
        assert await cb.allow_request() is True

    @pytest.mark.asyncio
    async def test_transitions_to_half_open(self):
        cb = CircuitBreaker('test', failure_threshold=1, recovery_timeout=0.01)
        await cb.record_failure()
        assert cb.state == CircuitState.OPEN
        await asyncio.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_half_open_allows_limited_requests(self):
        cb = CircuitBreaker('test', failure_threshold=1, recovery_timeout=0.01, half_open_max=1)
        await cb.record_failure()
        await asyncio.sleep(0.02)
        assert await cb.allow_request() is True  # first probe allowed
        assert await cb.allow_request() is False  # second blocked

    @pytest.mark.asyncio
    async def test_closes_on_success_after_half_open(self):
        cb = CircuitBreaker('test', failure_threshold=1, recovery_timeout=0.01)
        await cb.record_failure()
        await asyncio.sleep(0.02)
        await cb.allow_request()  # enter half_open
        await cb.record_success()
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_reopens_on_failure_in_half_open(self):
        cb = CircuitBreaker('test', failure_threshold=1, recovery_timeout=0.01)
        await cb.record_failure()
        await asyncio.sleep(0.02)
        await cb.allow_request()
        await cb.record_failure()
        assert cb._state == CircuitState.OPEN

    def test_get_health(self):
        cb = CircuitBreaker('test_cb')
        health = cb.get_health()
        assert health['name'] == 'test_cb'
        assert health['state'] == 'closed'
        assert health['failure_count'] == 0


# ============================================================================
# HttpClientManager Tests
# ============================================================================


class TestHttpClientManager:

    @pytest.mark.asyncio
    async def test_start_and_stop(self):
        mgr = HttpClientManager()
        await mgr.start()
        assert mgr._started is True
        assert mgr._client is not None
        await mgr.stop()
        assert mgr._started is False
        assert mgr._client is None

    @pytest.mark.asyncio
    async def test_double_start_idempotent(self):
        mgr = HttpClientManager()
        await mgr.start()
        client1 = mgr._client
        await mgr.start()
        assert mgr._client is client1
        await mgr.stop()

    @pytest.mark.asyncio
    async def test_client_property_raises_when_not_started(self):
        mgr = HttpClientManager()
        with pytest.raises(RuntimeError, match='not started'):
            _ = mgr.client

    @pytest.mark.asyncio
    async def test_client_property_returns_client(self):
        mgr = HttpClientManager()
        await mgr.start()
        assert isinstance(mgr.client, httpx.AsyncClient)
        await mgr.stop()

    def test_get_health(self):
        mgr = HttpClientManager()
        health = mgr.get_health()
        assert health['started'] is False
        assert 'circuit_breaker' in health


# ============================================================================
# Global Lifecycle Tests
# ============================================================================


class TestGlobalLifecycle:

    @pytest.mark.asyncio
    async def test_start_stop_http_client(self):
        import a2a_server.http_client as mod
        original = mod._manager

        try:
            mod._manager = None
            mgr = await start_http_client()
            assert mgr is not None
            assert get_http_client_manager() is mgr
            assert isinstance(get_http_client(), httpx.AsyncClient)

            await stop_http_client()
            assert get_http_client_manager() is None
        finally:
            mod._manager = original

    @pytest.mark.asyncio
    async def test_http_request_raises_when_not_started(self):
        import a2a_server.http_client as mod
        original = mod._manager
        try:
            mod._manager = None
            with pytest.raises(RuntimeError, match='not started'):
                await http_request('GET', '/test')
        finally:
            mod._manager = original

    @pytest.mark.asyncio
    async def test_get_http_client_raises_when_not_started(self):
        import a2a_server.http_client as mod
        original = mod._manager
        try:
            mod._manager = None
            with pytest.raises(RuntimeError, match='not started'):
                get_http_client()
        finally:
            mod._manager = original


# ============================================================================
# Request + Circuit Breaker Integration
# ============================================================================


class TestRequestIntegration:

    @pytest.mark.asyncio
    async def test_request_with_circuit_breaker_open(self):
        mgr = HttpClientManager()
        await mgr.start()

        # Force circuit open
        for _ in range(mgr._circuit.failure_threshold):
            await mgr._circuit.record_failure()

        with pytest.raises(CircuitBreakerOpenError):
            await mgr.request('GET', '/test')

        await mgr.stop()
