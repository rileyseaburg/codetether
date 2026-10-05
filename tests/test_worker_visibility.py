"""Mocked-local worker access contracts; no database or SSE network."""

import os

from datetime import UTC, datetime
from http import HTTPStatus
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from fastapi import FastAPI, HTTPException
from starlette.requests import Request


# Required at import time; all database operations below are mocked.
os.environ.setdefault(
    'DATABASE_URL', 'postgresql://test:test@localhost/worker_test'
)

from a2a_server import database, policy, worker_sse, worker_visibility


OWNER = {'id': 'user-a', 'tenant_id': 'tenant-a', 'roles': ['viewer']}
WORKERS = [
    {'worker_id': 'own', 'agent_name': 'own-agent'},
    {'worker_id': 'foreign', 'agent_name': 'foreign-agent'},
    {'worker_id': 'unassigned', 'agent_name': 'unassigned-agent'},
    {'worker_id': 'unknown', 'agent_name': 'unknown-agent'},
]
OWNERSHIP = [
    {'worker_id': 'own', 'tenant_id': 'tenant-a'},
    # Reject out-of-scope rows even if a future query accidentally returns them.
    {'worker_id': 'foreign', 'tenant_id': 'tenant-b'},
    {'worker_id': 'unassigned', 'tenant_id': None},
]


def request_for(user=None):
    request = Request({'type': 'http', 'headers': []})
    if user is not None:
        request.state.user = user
    return request


@pytest.fixture
def ownership(monkeypatch):
    enforce = AsyncMock()
    lookup = AsyncMock(return_value=OWNERSHIP)
    monkeypatch.setattr(policy, 'enforce_policy', enforce)
    monkeypatch.setattr(database, 'db_list_workers', lookup)
    return SimpleNamespace(enforce=enforce, lookup=lookup)


@pytest.mark.asyncio
async def test_verified_tenant_intersects_durable_ownership(ownership):
    request = request_for(OWNER)
    request.state.tenant_id = 'tenant-b'  # Routing state is not authority.
    assert await worker_visibility.filter_connected_workers(
        request, WORKERS
    ) == [WORKERS[0]]
    ownership.enforce.assert_awaited_once_with(
        user=OWNER, action='workers:read'
    )
    ownership.lookup.assert_awaited_once_with(tenant_id='tenant-a', strict=True)


@pytest.mark.asyncio
async def test_unscoped_user_is_not_fleet_admin(ownership):
    request = request_for({'id': 'user-a', 'roles': ['viewer']})
    request.state.tenant_id = 'tenant-a'
    with pytest.raises(HTTPException) as exc:
        await worker_visibility.visible_worker_ids(request)
    assert exc.value.status_code == HTTPStatus.FORBIDDEN
    ownership.lookup.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('user', [None, {'id': 'admin', 'roles': ['admin']}])
async def test_authenticated_infrastructure_and_unscoped_admin_fleet_access(
    ownership, user
):
    # Infrastructure reaches this helper only after worker authentication.
    assert (
        await worker_visibility.filter_connected_workers(
            request_for(user), WORKERS
        )
        == WORKERS
    )
    ownership.lookup.assert_not_awaited()


@pytest.mark.asyncio
async def test_tenant_admin_remains_scoped(ownership):
    user = {**OWNER, 'roles': ['admin']}
    assert await worker_visibility.visible_worker_ids(request_for(user)) == {
        'own'
    }
    ownership.lookup.assert_awaited_once_with(tenant_id='tenant-a', strict=True)


@pytest.mark.asyncio
async def test_policy_denial_does_not_query_ownership(ownership):
    ownership.enforce.side_effect = HTTPException(
        status_code=HTTPStatus.FORBIDDEN
    )
    with pytest.raises(HTTPException) as exc:
        await worker_visibility.visible_worker_ids(request_for(OWNER))
    assert exc.value.status_code == HTTPStatus.FORBIDDEN
    ownership.lookup.assert_not_awaited()


@pytest.mark.asyncio
async def test_spiffe_uses_verified_workload_authority(monkeypatch, ownership):
    request = request_for()
    request.state.spiffe = SimpleNamespace(spiffe_id='spiffe://test/worker')
    workload = {**OWNER, 'auth_source': 'spiffe'}
    resolve = AsyncMock(return_value=workload)
    monkeypatch.setattr(policy, '_resolve_user', resolve)
    assert await worker_visibility.visible_worker_ids(request) == {'own'}
    resolve.assert_awaited_once_with(request)
    ownership.enforce.assert_awaited_once_with(
        user=workload, action='workers:read'
    )


@pytest.mark.asyncio
@pytest.mark.parametrize('user', [None, OWNER])
async def test_spiffe_cannot_fall_back_to_platform_authority(
    monkeypatch, ownership, user
):
    request = request_for()
    request.state.spiffe = SimpleNamespace(spiffe_id='spiffe://test/worker')
    monkeypatch.setattr(policy, '_resolve_user', AsyncMock(return_value=user))
    with pytest.raises(HTTPException) as exc:
        await worker_visibility.visible_worker_ids(request)
    assert exc.value.status_code == HTTPStatus.FORBIDDEN
    ownership.lookup.assert_not_awaited()


@pytest.fixture
def app(monkeypatch):
    async def authenticate(request):
        request.state.user = OWNER
        return OWNER['id']

    monkeypatch.setattr(worker_sse, '_verify_worker_or_user_auth', authenticate)
    now = datetime.now(UTC)
    workers = {
        row['worker_id']: SimpleNamespace(
            **row,
            connected_at=now,
            last_heartbeat=now,
            is_busy=False,
            current_task_id=None,
            capabilities=['chat'],
            codebases=set(),
        )
        for row in WORKERS
    }
    registry = SimpleNamespace(
        list_workers=AsyncMock(return_value=WORKERS),
        get_worker=AsyncMock(side_effect=workers.get),
    )
    monkeypatch.setattr(worker_sse, 'get_worker_registry', lambda: registry)
    app = FastAPI()
    app.include_router(worker_sse.worker_sse_router)
    return app


@pytest.mark.asyncio
async def test_http_list_and_owned_detail(app, ownership):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url='http://test'
    ) as client:
        response = await client.get('/v1/worker/connected')
        assert response.status_code == HTTPStatus.OK
        assert response.json()['workers'] == [WORKERS[0]]
        assert response.json()['count'] == 1
        response = await client.get('/v1/worker/connected/own')
        assert response.status_code == HTTPStatus.OK
        assert response.json()['agent_name'] == 'own-agent'


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'worker_id', ['foreign', 'unassigned', 'unknown', 'missing']
)
async def test_http_foreign_and_missing_details_are_not_found(
    app, ownership, worker_id
):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url='http://test'
    ) as client:
        response = await client.get(f'/v1/worker/connected/{worker_id}')
    assert response.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
@pytest.mark.parametrize('suffix', ['', '/own'])
async def test_http_ownership_outage_is_not_empty_success(
    app, ownership, suffix
):
    ownership.lookup.side_effect = RuntimeError(
        'ownership database unavailable'
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url='http://test'
    ) as client:
        response = await client.get(f'/v1/worker/connected{suffix}')
    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert response.json()['detail'] == 'Worker ownership service unavailable'


@pytest.mark.asyncio
@pytest.mark.parametrize('suffix', ['', '/own'])
async def test_http_authentication_failure_stops_discovery(
    app, ownership, monkeypatch, suffix
):
    authenticate = AsyncMock(
        side_effect=HTTPException(status_code=HTTPStatus.UNAUTHORIZED)
    )
    monkeypatch.setattr(worker_sse, '_verify_worker_or_user_auth', authenticate)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url='http://test'
    ) as client:
        response = await client.get(f'/v1/worker/connected{suffix}')
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    ownership.lookup.assert_not_awaited()
    ownership.enforce.assert_not_awaited()


@pytest.mark.asyncio
async def test_database_strict_mode_distinguishes_missing_pool(monkeypatch):
    monkeypatch.setattr(database, 'get_pool', AsyncMock(return_value=None))
    assert await database.db_list_workers() == []
    with pytest.raises(RuntimeError, match='Worker database unavailable'):
        await database.db_list_workers(tenant_id='tenant-a', strict=True)


@pytest.mark.asyncio
async def test_database_strict_mode_propagates_query_failure(monkeypatch):
    pool = MagicMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(
        side_effect=RuntimeError('connection unavailable')
    )
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(database, 'get_pool', AsyncMock(return_value=pool))
    assert await database.db_list_workers() == []
    with pytest.raises(RuntimeError, match='connection unavailable'):
        await database.db_list_workers(tenant_id='tenant-a', strict=True)
