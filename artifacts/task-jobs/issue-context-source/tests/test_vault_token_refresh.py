"""Mocked-local coverage of Vault authentication expiry and bounded recovery."""
# ruff: noqa: SLF001, PLR2004

import asyncio

from collections import deque
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from a2a_server import vault_client as vault


def login(token, lease=100):
    return 200, {'auth': {'client_token': token, 'lease_duration': lease}}


INVALID = (
    403,
    {
        'errors': [
            '2 errors occurred:\n\t* permission denied\n\t* invalid token\n\n'
        ]
    },
)
OK = 200, {'data': {'data': {'result': 'stored'}}}


class Response:
    def __init__(self, status, body):
        self.status = status
        self.body = body

    async def json(self):
        if isinstance(self.body, Exception):
            raise self.body
        return self.body


class Session:
    """Capture requests without network access or real credentials."""

    def __init__(self):
        self.logins = deque()
        self.replies = deque()
        self.auth_calls = []
        self.calls = []
        self.handler = None

    @asynccontextmanager
    async def post(self, url, *, json, allow_redirects):
        assert allow_redirects is False
        self.auth_calls.append((url, json))
        await asyncio.sleep(0)
        reply = self.logins.popleft()
        if isinstance(reply, Exception):
            raise reply
        yield Response(*reply)

    @asynccontextmanager
    async def request(self, method, url, **kwargs):
        assert kwargs['allow_redirects'] is False
        self.calls.append((method, url, kwargs))
        reply = (
            await self.handler(kwargs)
            if self.handler
            else self.replies.popleft()
        )
        if isinstance(reply, Exception):
            raise reply
        yield Response(*reply)


@pytest.fixture
def env(monkeypatch, tmp_path):
    jwt = tmp_path / 'jwt'
    jwt.write_text('mock-jwt-1')
    clock = SimpleNamespace(now=1000.0)
    session = Session()
    monkeypatch.setattr(vault, '_kubernetes_tokens', {})
    monkeypatch.setattr(vault, 'VAULT_TOKEN', '')
    monkeypatch.setattr(vault, 'K8S_TOKEN_PATH', str(jwt))
    monkeypatch.setattr(
        vault, 'time', SimpleNamespace(monotonic=lambda: clock.now)
    )
    monkeypatch.setattr(
        vault.VaultClient, '_get_session', AsyncMock(return_value=session)
    )
    return SimpleNamespace(session=session, clock=clock, jwt=jwt)


@pytest.mark.asyncio
async def test_expiry_refresh_is_shared_and_reads_rotated_jwt(env):
    env.session.logins.extend([login('old'), login('new')])
    first, second = vault.VaultClient(), vault.VaultClient()
    assert await first._get_token() == 'old'
    env.clock.now += 89
    assert await second._get_token() == 'old'
    env.jwt.write_text('mock-jwt-2')
    env.clock.now += 1
    assert await second._get_token() == 'new'
    assert await first._get_token() == 'new'
    assert len(env.session.auth_calls) == 2
    assert env.session.auth_calls[-1][1]['jwt'] == 'mock-jwt-2'


@pytest.mark.asyncio
async def test_auth_scope_isolates_address_role_and_jwt(env, monkeypatch):
    env.session.logins.extend(login(f'token-{i}') for i in range(4))
    first = vault.VaultClient('https://vault-one')
    second = vault.VaultClient('https://vault-two')
    monkeypatch.setattr(vault, 'VAULT_ROLE', 'different-role')
    third = vault.VaultClient('https://vault-one')
    other_jwt = env.jwt.parent / 'other-jwt'
    other_jwt.write_text('mock-other-jwt')
    monkeypatch.setattr(vault, 'K8S_TOKEN_PATH', str(other_jwt))
    fourth = vault.VaultClient('https://vault-one')
    for index, client in enumerate([first, second, third, fourth]):
        assert await client._get_token() == f'token-{index}'
    assert len(env.session.auth_calls) == 4


@pytest.mark.asyncio
@pytest.mark.parametrize('method', ['GET', 'POST', 'DELETE'])
async def test_explicit_invalid_token_retries_once(env, method):
    env.session.logins.extend([login('old'), login('new')])
    env.session.replies.extend([INVALID, OK])
    client = vault.VaultClient()
    assert (
        await client._request(method, 'secret/data/item', {'value': 1}) == OK[1]
    )
    assert [c[2]['headers']['X-Vault-Token'] for c in env.session.calls] == [
        'old',
        'new',
    ]
    assert all(c[2]['json'] == {'value': 1} for c in env.session.calls)
    assert await client._get_token(rejected_token='old') == 'new'
    assert len(env.session.auth_calls) == 2


@pytest.mark.asyncio
async def test_concurrent_rejections_reauthenticate_only_once(env):
    env.session.logins.extend([login('old'), login('new')])
    ready = asyncio.Event()
    old_requests = 0

    async def reply(kwargs):
        nonlocal old_requests
        if kwargs['headers']['X-Vault-Token'] == 'old':
            old_requests += 1
            if old_requests == 2:
                ready.set()
            await ready.wait()
            return INVALID
        return OK

    env.session.handler = reply
    clients = [vault.VaultClient(), vault.VaultClient()]
    results = await asyncio.wait_for(
        asyncio.gather(
            *[client._request('POST', 'secret/data/item') for client in clients]
        ),
        timeout=2,
    )
    assert results == [OK[1], OK[1]]
    assert len(env.session.auth_calls) == 2
    assert len(env.session.calls) == 4


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'response',
    [
        (403, {'errors': ['permission denied']}),
        (403, {'errors': ['invalid token in unrelated text']}),
        (403, ValueError('mock-raw-response')),
        (401, {'errors': ['invalid token']}),
        (500, {'errors': ['invalid token']}),
        (307, {'errors': ['redirect elsewhere']}),
    ],
)
async def test_non_auth_denials_never_retry_writes(env, response):
    env.session.logins.append(login('valid'))
    env.session.replies.append(response)
    assert await vault.VaultClient().write_secret('item', {'value': 1}) is False
    assert len(env.session.calls) == 1
    assert len(env.session.auth_calls) == 1


@pytest.mark.asyncio
async def test_static_token_never_substitutes_kubernetes_identity(
    env, monkeypatch
):
    env.session.logins.append(login('k8s-cached'))
    assert await vault.VaultClient()._get_token() == 'k8s-cached'
    monkeypatch.setattr(vault, 'VAULT_TOKEN', 'static-token')
    env.session.replies.append(INVALID)
    assert await vault.VaultClient().write_secret('item', {}) is False
    assert env.session.calls[0][2]['headers']['X-Vault-Token'] == 'static-token'
    assert len(env.session.calls) == len(env.session.auth_calls) == 1


@pytest.mark.asyncio
async def test_second_rejection_is_bounded_and_retires_bad_token(env):
    env.session.logins.extend([login('old'), login('also-invalid')])
    env.session.replies.extend([INVALID, INVALID])
    client = vault.VaultClient()
    assert await client.write_secret('item', {}) is False
    assert await vault.VaultClient().write_secret('item', {}) is False
    assert client._auth_state.token is None
    assert len(env.session.calls) == len(env.session.auth_calls) == 2


@pytest.mark.asyncio
async def test_login_failure_is_shared_but_not_cached_forever(env):
    env.session.logins.extend(
        [(403, {'errors': ['denied']}), login('recovered')]
    )
    results = await asyncio.gather(
        *[vault.VaultClient()._get_token() for _ in range(8)]
    )
    assert results == [None] * 8
    assert len(env.session.auth_calls) == 1
    env.clock.now += 1
    assert await vault.VaultClient()._get_token() == 'recovered'


@pytest.mark.asyncio
async def test_no_raw_response_or_credential_in_logs(env, caplog):
    marker = 'mock-sensitive-response-jwt-api-key'
    env.session.logins.append((403, {'errors': [marker]}))
    assert await vault.VaultClient()._get_token() is None
    env.clock.now += 1
    env.session.logins.append(RuntimeError(marker))
    assert await vault.VaultClient()._get_token() is None
    env.clock.now += 1
    env.session.logins.append(login(marker))
    env.session.replies.extend(
        [(500, {'errors': [marker]}), RuntimeError(marker)]
    )
    client = vault.VaultClient()
    assert (
        await client._request('POST', 'secret/data/item', {'key': marker})
        is None
    )
    assert (
        await client._request('POST', 'secret/data/item', {'key': marker})
        is None
    )
    assert marker not in caplog.text
    assert marker not in repr(client._auth_state)
    assert len(env.session.calls) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize('lease', [0, None])
async def test_missing_or_zero_lease_has_bounded_cache(env, lease):
    env.session.logins.extend([login('old', lease), login('new')])
    client = vault.VaultClient()
    assert await client._get_token() == 'old'
    env.clock.now += vault._MAX_CACHE_SECONDS
    assert await client._get_token() == 'new'


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'lease', [-1, float('nan'), float('inf'), 'not-a-lease']
)
async def test_invalid_lease_is_not_cached(env, lease):
    env.session.logins.append(login('invalid-lease-token', lease))
    client = vault.VaultClient()
    assert await client._get_token() is None
    assert client._auth_state.token is None


@pytest.mark.asyncio
async def test_failed_refresh_is_single_flight_for_concurrent_rejections(env):
    env.session.logins.extend([login('old'), (403, {'errors': ['denied']})])
    both_sent = asyncio.Event()
    sent = 0

    async def reply(kwargs):
        nonlocal sent
        sent += 1
        if sent == 2:
            both_sent.set()
        await both_sent.wait()
        return INVALID

    env.session.handler = reply
    results = await asyncio.wait_for(
        asyncio.gather(
            *[vault.VaultClient().write_secret('item', {}) for _ in range(2)]
        ),
        timeout=2,
    )
    assert results == [False, False]
    assert len(env.session.calls) == 2
    assert len(env.session.auth_calls) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize('status,expected', [(204, {}), (404, None)])
async def test_existing_response_semantics_are_preserved(env, status, expected):
    env.session.logins.append(login('valid'))
    env.session.replies.append((status, None))
    assert (
        await vault.VaultClient()._request('GET', 'secret/data/item')
        == expected
    )
    assert len(env.session.calls) == 1


@pytest.mark.asyncio
async def test_missing_jwt_fails_closed_without_network(env):
    env.jwt.unlink()
    assert await vault.VaultClient()._get_token() is None
    assert env.session.auth_calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'auth', [{}, {'client_token': ''}, {'client_token': 123}]
)
async def test_malformed_login_never_populates_cache(env, auth):
    env.session.logins.append((200, {'auth': auth}))
    client = vault.VaultClient()
    assert await client._get_token() is None
    assert client._auth_state.token is None
