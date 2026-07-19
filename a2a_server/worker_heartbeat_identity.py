"""Canonical worker binding for heartbeat updates."""

from collections.abc import Mapping

from a2a_server.worker_registration_identity import bind as bind_identity


def bind(
    headers: Mapping[str, str],
    worker_id: str,
    worker: Mapping[str, object],
) -> dict[str, object]:
    """Verify canonical liveness and return trusted worker data."""
    value = dict(worker)
    name = str(value.get('name') or '')
    if not name.startswith('ctforgejo_'):
        return value
    capabilities, tenant_id = bind_identity(
        headers,
        worker_id,
        name,
        list(value.get('capabilities') or []),
        proof=('heartbeat', ''),
    )
    value['capabilities'] = capabilities
    value['tenant_id'] = tenant_id
    return value
