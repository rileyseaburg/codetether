from types import SimpleNamespace

import pytest

from a2a_server import worker_sse


class Registry:
    def __init__(self) -> None:
        self.released = False

    async def claim_task(self, _task_id: str, _worker_id: str) -> bool:
        return True

    async def release_task(self, _task_id: str, _worker_id: str) -> bool:
        self.released = True
        return True


@pytest.mark.asyncio
async def test_claim_endpoint_rolls_back_a_lost_durable_race(monkeypatch):
    registry = Registry()

    async def verified(*_args: object, **_kwargs: object) -> bool:
        return True

    async def unavailable(*_args: object) -> str:
        return 'unavailable'

    monkeypatch.setattr(worker_sse, '_verify_auth', lambda _request: None)
    monkeypatch.setattr(worker_sse, 'require_forgejo_worker_claim', verified)
    monkeypatch.setattr(worker_sse, 'reserve_forgejo_claim', unavailable)
    monkeypatch.setattr(worker_sse, 'get_worker_registry', lambda: registry)
    request = SimpleNamespace(headers={})
    claim = worker_sse.TaskClaimRequest(task_id='cttask_1')
    with pytest.raises(worker_sse.HTTPException) as raised:
        await worker_sse.claim_task(
            request, claim, worker_id='worker-1', x_worker_id=None
        )
    assert raised.value.status_code == 409  # noqa: PLR2004
    assert registry.released
