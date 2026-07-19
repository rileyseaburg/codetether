import asyncio

from contextlib import asynccontextmanager

import pytest

import a2a_server.forgejo_author_authenticate as authentication
import a2a_server.forgejo_author_service as service

from tests.forgejo_service_fixture import provenance_key, request


@pytest.mark.asyncio
async def test_concurrent_retries_create_one_durable_task(monkeypatch):
    lock = asyncio.Lock()
    state = {'task': None, 'creates': 0}

    @asynccontextmanager
    async def serialized(_metadata):
        async with lock:
            yield

    async def prepare(_metadata):
        return 'cttask_fixed', state['task']

    async def validate(_metadata, *, strict):
        assert strict is True

    async def verify(_metadata, _token):
        return provenance_key()

    class Bridge:
        async def create_task(self, **_kwargs):
            state['creates'] += 1
            await asyncio.sleep(0)
            state['task'] = {'id': 'cttask_fixed'}
            return state['task']

    monkeypatch.setattr(service, 'serialized', serialized)
    monkeypatch.setattr(service, 'prepare', prepare)
    monkeypatch.setattr(authentication, 'verify', verify)
    calls = [service.create(Bridge(), request(), validate) for _ in range(2)]
    results = await asyncio.gather(*calls)
    assert state['creates'] == 1
    assert results == [{'id': 'cttask_fixed'}, {'id': 'cttask_fixed'}]
