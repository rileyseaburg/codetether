from types import SimpleNamespace

import pytest

from a2a_server import monitor_api
from tests.forgejo_metadata import metadata
from tests.forgejo_provenance_fixture import registry


class Item:
    def __init__(self, value: dict[str, object]) -> None:
        self.value = value

    def to_dict(self) -> dict[str, object]:
        return self.value


class Bridge:
    def __init__(self, value: dict[str, object]) -> None:
        self.item = Item(value)
        self.cancelled = False

    async def get_task(self, _task_id: str) -> Item:
        return self.item

    def cancel_task(self, _task_id: str) -> bool:
        self.cancelled = True
        return True


@pytest.mark.asyncio
async def test_read_and_cancel_reject_an_unbound_principal(monkeypatch):
    value = metadata()
    value.update(author_identity_key_id='author-key', tenant_id='tenant')
    bridge = Bridge({'id': 'cttask_1', 'metadata': value})
    request = SimpleNamespace(
        headers={'authorization': 'Bearer other-token'},
        state=SimpleNamespace(),
    )
    monkeypatch.setenv('CODETETHER_PROVENANCE_SIGNING_KEYS', registry(value))
    monkeypatch.setenv('A2A_AUTH_TOKENS', 'other:other-token')
    monkeypatch.setattr(monitor_api, 'get_agent_bridge', lambda: bridge)
    with pytest.raises(monitor_api.HTTPException):
        await monitor_api.get_task('cttask_1', request)
    with pytest.raises(monitor_api.HTTPException):
        await monitor_api.cancel_task('cttask_1', request)
    with pytest.raises(monitor_api.HTTPException):
        await monitor_api.get_task_output('cttask_1', request)
    with pytest.raises(monitor_api.HTTPException):
        await monitor_api.stream_task_output_sse('cttask_1', request)
    assert not bridge.cancelled
