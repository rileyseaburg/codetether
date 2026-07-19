import pytest

from fastapi import HTTPException

from a2a_server import database
from a2a_server.worker_extended_claim import resolve


@pytest.mark.asyncio
async def test_extended_claim_rejects_canonical_workers(monkeypatch):
    async def worker(_worker_id: str) -> dict[str, object]:
        return {'name': 'ctforgejo_canonical'}

    monkeypatch.setattr(database, 'db_get_worker', worker)
    with pytest.raises(HTTPException) as raised:
        await resolve('worker-1', 'ctforgejo_canonical')
    assert raised.value.status_code == 409  # noqa: PLR2004


@pytest.mark.asyncio
async def test_extended_claim_uses_the_durable_generic_name(monkeypatch):
    async def worker(_worker_id: str) -> dict[str, object]:
        return {'name': 'generic-worker'}

    monkeypatch.setattr(database, 'db_get_worker', worker)
    assert await resolve('worker-1', None) == 'generic-worker'
    with pytest.raises(HTTPException) as raised:
        await resolve('worker-1', 'ctforgejo_spoofed')
    assert raised.value.status_code == 403  # noqa: PLR2004
