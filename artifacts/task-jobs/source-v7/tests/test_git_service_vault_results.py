from __future__ import annotations

from typing import Any

import pytest

from a2a_server import git_service, vault_client


class _VaultClient:
    def __init__(self, write_result: bool) -> None:
        self.write_result = write_result
        self.writes: list[tuple[str, dict[str, Any]]] = []

    async def write_secret(self, path: str, data: dict[str, Any]) -> bool:
        self.writes.append((path, data))
        return self.write_result


@pytest.mark.asyncio
@pytest.mark.parametrize('write_result', [True, False])
async def test_store_git_credentials_propagates_vault_result(
    monkeypatch: pytest.MonkeyPatch, write_result: bool
) -> None:
    client = _VaultClient(write_result)
    monkeypatch.setattr(vault_client, 'get_vault_client', lambda: client)

    stored = await git_service.store_git_credentials(
        'workspace-1', 'secret-token', 'forgejo_pat'
    )

    assert stored is write_result
    assert client.writes == [
        (
            'codetether/git/workspace-1',
            {'token': 'secret-token', 'token_type': 'forgejo_pat'},
        )
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize('write_result', [True, False])
async def test_store_git_credential_record_propagates_vault_result(
    monkeypatch: pytest.MonkeyPatch, write_result: bool
) -> None:
    client = _VaultClient(write_result)
    monkeypatch.setattr(vault_client, 'get_vault_client', lambda: client)
    record = {
        'token': 'secret-token',
        'token_type': 'forgejo_pat',
        'git_url': 'https://forgejo.example/owner/repo.git',
    }

    stored = await git_service.store_git_credential_record(
        'workspace-2', record
    )

    assert stored is write_result
    assert client.writes == [
        ('codetether/git/workspace-2', record)
    ]