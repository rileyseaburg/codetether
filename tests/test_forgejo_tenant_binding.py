from types import SimpleNamespace

import pytest

from a2a_server import database
from a2a_server.forgejo_author_task import prepare, task_identity
from a2a_server.forgejo_request_scope import resolve
from tests.forgejo_metadata import metadata


def test_authenticated_tenants_have_distinct_task_identities():
    first, second = metadata(), metadata()
    first['idempotency_scope'] = 'tenant:first'
    second['idempotency_scope'] = 'tenant:second'
    assert task_identity(first) != task_identity(second)


def test_request_tenant_overrides_client_scope():
    request = SimpleNamespace(
        state=SimpleNamespace(
            policy_user={'tenant_id': 'tenant-a', 'id': 'user'}
        )
    )
    assert resolve(request) == ('tenant:tenant-a', 'tenant-a')


@pytest.mark.asyncio
async def test_worker_lookup_is_tenant_scoped(monkeypatch):
    seen = []

    async def get_pool():
        return object()

    async def get_task(_task_id):
        return None

    async def get_worker(_name, *, tenant_id=None):
        seen.append(tenant_id)
        return {
            'worker_id': 'worker-1',
            'tenant_id': tenant_id,
            'capabilities': ['codetether-identity-key:author-key'],
        }

    monkeypatch.setattr(database, 'get_pool', get_pool)
    monkeypatch.setattr(database, 'db_get_task', get_task)
    monkeypatch.setattr(database, 'db_get_active_worker_by_name', get_worker)
    value = metadata()
    value['tenant_id'] = 'tenant-a'
    value['author_identity_key_id'] = 'author-key'
    value['author_identity_key_id'] = 'author-key'
    value['author_identity_key_id'] = 'author-key'
    value['author_identity_key_id'] = 'author-key'
    value['author_identity_key_id'] = 'author-key'
    value['author_identity_key_id'] = 'author-key'
    value['author_identity_key_id'] = 'author-key'
    value['author_identity_key_id'] = 'author-key'
    value['author_identity_key_id'] = 'author-key'
    value['author_identity_key_id'] = 'author-key'
    await prepare(value)
    assert seen == ['tenant-a']
    assert value['idempotency_key'].startswith('cttask_')
    assert 'tenant-a' not in value['idempotency_key']
