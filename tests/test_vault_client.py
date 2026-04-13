import pytest
from unittest.mock import AsyncMock

from a2a_server.vault_client import VaultClient


class _Resp:
    def __init__(self, status, body):
        self.status = status
        self._body = body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def json(self):
        return self._body

    async def text(self):
        return str(self._body)


@pytest.mark.asyncio
async def test_vault_request_retries_after_auth_failure():
    client = VaultClient(addr="http://vault.test")
    client._token = "stale"
    seen = []

    async def fake_get_token():
        if client._token is None:
            client._token = "fresh"
        return client._token

    class _Session:
        def request(self, _method, _url, headers=None, json=None):
            seen.append(headers["X-Vault-Token"])
            return _Resp(403, "invalid token") if len(seen) == 1 else _Resp(200, {"ok": True})

    client._get_token = fake_get_token  # type: ignore[method-assign]
    client._get_session = AsyncMock(return_value=_Session())  # type: ignore[method-assign]

    result = await client._request("GET", "secret/data/demo")

    assert result == {"ok": True}
    assert seen == ["stale", "fresh"]
