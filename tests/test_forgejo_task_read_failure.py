import pytest

from a2a_server import database
from a2a_server.forgejo_author_task import prepare
from tests.forgejo_metadata import metadata


@pytest.mark.asyncio
async def test_prepare_propagates_durable_read_failures(monkeypatch):
    async def get_pool():
        return object()

    async def failed_read(_task_id):
        raise OSError('database read failed')

    monkeypatch.setattr(database, 'get_pool', get_pool)
    monkeypatch.setattr(database, 'db_get_task', failed_read)
    with pytest.raises(OSError, match='database read failed'):
        await prepare(metadata())
