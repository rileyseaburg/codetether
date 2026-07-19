import pytest

from a2a_server import database
from a2a_server.forgejo_author_task import prepare
from tests.forgejo_metadata import metadata


def install_database(monkeypatch, *, pool=True, task=None, worker=None):
    async def get_pool():
        return object() if pool else None

    async def get_task(_task_id):
        return task

    async def get_worker(_name, *, tenant_id=None):
        return worker

    monkeypatch.setattr(database, 'get_pool', get_pool)
    monkeypatch.setattr(database, 'db_get_task', get_task)
    monkeypatch.setattr(database, 'db_get_active_worker_by_name', get_worker)


@pytest.mark.asyncio
async def test_prepare_fails_closed_without_durable_storage(monkeypatch):
    install_database(monkeypatch, pool=False)
    with pytest.raises(RuntimeError, match='durable'):
        await prepare(metadata())


@pytest.mark.asyncio
async def test_prepare_reuses_the_deterministic_task(monkeypatch):
    existing = {'id': 'existing-task'}
    install_database(monkeypatch, task=existing)
    _task_id, result = await prepare(metadata())
    assert result == existing


@pytest.mark.asyncio
async def test_prepare_binds_the_canonical_active_worker(monkeypatch):
    value = metadata()
    value.update(author_identity_key_id='author-key', tenant_id='tenant')
    worker = {
        'worker_id': 'worker-1',
        'tenant_id': 'tenant',
        'capabilities': ['codetether-identity-key:author-key'],
    }
    install_database(monkeypatch, worker=worker)
    _task_id, existing = await prepare(value)
    assert existing is None
