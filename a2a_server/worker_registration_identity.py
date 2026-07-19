"""Trusted identity fields for canonical worker registration."""

from collections.abc import Mapping, Sequence

from a2a_server.worker_identity_proof import verify


PREFIX = 'ctforgejo_'


def bind(
    headers: Mapping[str, str],
    worker_id: str,
    name: str,
    capabilities: Sequence[str],
    *,
    proof: tuple[str, str] = ('register', ''),
) -> tuple[list[str], str | None]:
    """Return trusted tenancy after canonical-route key possession."""
    values = list(capabilities)
    if not name.startswith(PREFIX):
        return values, None
    key = verify(headers, proof[0], worker_id, name, proof[1])
    marker = f'codetether-identity-key:{key.key_id}'
    if marker not in values:
        values.append(marker)
    return values, key.tenant_id
