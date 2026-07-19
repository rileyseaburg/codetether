"""Canonical identities for configured Forgejo agent principals."""

import hashlib
import re


_COMPONENT = re.compile(r'^[a-z0-9][a-z0-9._-]{0,127}$')
_HOST = re.compile(r'^[a-z0-9][a-z0-9.:-]{0,127}$')


def canonical_identity(host: str, login: str, slot: str) -> str:
    """Derive a stable route from one verified Forgejo principal."""
    host, login, slot = host.lower(), login.lower(), slot.lower()
    if not _HOST.fullmatch(host) or not all(
        _COMPONENT.fullmatch(value) for value in (login, slot)
    ):
        raise ValueError('unsafe Forgejo principal')
    digest = hashlib.sha256(f'{host}\n{login}\n{slot}'.encode()).hexdigest()
    return f'ctforgejo_{digest[:40]}'
