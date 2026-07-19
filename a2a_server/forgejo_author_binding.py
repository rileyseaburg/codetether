"""Server-controlled tenancy for a verified author binding."""

from collections.abc import MutableMapping

from a2a_server.forgejo_provenance_keys import ProvenanceKey


def apply(metadata: MutableMapping[str, object], key: ProvenanceKey) -> None:
    """Replace client aliases with the key's trusted tenant and identity."""
    requested_tenant = str(metadata.get('tenant_id') or '')
    if requested_tenant and requested_tenant != key.tenant_id:
        raise ValueError(
            'authenticated tenant does not match author provenance'
        )
    metadata['tenant_id'] = key.tenant_id
    metadata['idempotency_scope'] = f'tenant:{key.tenant_id}'
    metadata['author_identity_key_id'] = key.key_id
    metadata['server_author_binding_verified'] = True
