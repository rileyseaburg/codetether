"""Durable worker checks for a verified author task."""

from collections.abc import Mapping


def require(
    worker: Mapping[str, object], metadata: Mapping[str, object]
) -> None:
    """Require the selected worker to own the task key and tenant."""
    key_id = str(metadata.get('author_identity_key_id') or '')
    marker = f'codetether-identity-key:{key_id}'
    capabilities = worker.get('capabilities')
    if not isinstance(capabilities, list) or marker not in capabilities:
        raise LookupError('canonical author worker identity is not verified')
    tenant = str(metadata.get('tenant_id') or '')
    if str(worker.get('tenant_id') or '') != tenant:
        raise LookupError('canonical author worker tenant does not match')
