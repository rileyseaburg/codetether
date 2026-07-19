"""Ordered collaborators for author service tests."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Protocol

from pytest import MonkeyPatch

import a2a_server.forgejo_author_service as service
import a2a_server.forgejo_author_authenticate as authentication

from tests.forgejo_service_fixture import provenance_key


class Validator(Protocol):
    """Worker validator accepted by the service under test."""
    async def __call__(self, metadata: object, *, strict: bool) -> None: ...


def install(monkeypatch: MonkeyPatch, events: list[str]) -> Validator:
    """Install recording collaborators and return the worker validator."""
    @asynccontextmanager
    async def gate(_metadata: object) -> AsyncIterator[None]:
        events.append('lock')
        yield
        events.append('unlock')

    async def prepare(_metadata: object) -> tuple[str, None]:
        return 'cttask_fixed', None

    async def validate(_metadata: object, *, strict: bool) -> None:
        assert strict is True
        events.append('validate')

    async def verify(_metadata: object, token: str) -> SimpleNamespace:
        assert token == 'forgejo-token'
        events.append('verify')
        return provenance_key()

    monkeypatch.setattr(service, 'serialized', gate)
    monkeypatch.setattr(service, 'prepare', prepare)
    monkeypatch.setattr(authentication, 'verify', verify)
    return validate
