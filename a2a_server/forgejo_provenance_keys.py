"""Configured verification keys for author provenance."""

import json
import os

from dataclasses import dataclass


@dataclass(frozen=True)
class ProvenanceKey:
    """One key bound to a canonical agent and tenant."""

    key_id: str
    secret: str
    agent_identity: str
    tenant_id: str
    task_auth_label: str | None


def resolve(key_id: str) -> ProvenanceKey:
    """Resolve one required key from server-only JSON configuration."""
    raw = os.environ.get('CODETETHER_PROVENANCE_SIGNING_KEYS', '')
    if not raw:
        raise RuntimeError(
            'CodeTether provenance verification is not configured'
        )
    try:
        values = json.loads(raw)
        value = values.get(key_id) if isinstance(values, dict) else None
    except (TypeError, ValueError) as error:
        raise RuntimeError(
            'CodeTether provenance key configuration is invalid'
        ) from error
    if not isinstance(value, dict):
        raise ValueError('CodeTether provenance key is not trusted')
    secret = _field(value, 'secret')
    identity = _field(value, 'agent_identity')
    tenant = _field(value, 'tenant_id')
    auth_label = _field(value, 'task_auth_label')
    if not secret or not identity or not tenant:
        raise RuntimeError('CodeTether provenance key binding is incomplete')
    return ProvenanceKey(key_id, secret, identity, tenant, auth_label or None)


def _field(value: dict[object, object], field: str) -> str:
    return str(value.get(field) or '').strip()
