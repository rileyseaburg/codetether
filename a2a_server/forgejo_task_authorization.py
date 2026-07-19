"""Task-principal authorization for a verified provenance key."""

from a2a_server.forgejo_provenance_keys import ProvenanceKey


def require(key: ProvenanceKey, scope: str, tenant_id: str | None) -> None:
    """Require the task credential to belong to the key's trusted principal."""
    if tenant_id is not None:
        if tenant_id != key.tenant_id:
            raise ValueError(
                'task credential tenant does not match provenance key'
            )
        return
    if key.task_auth_label is not None:
        if not scope.startswith(f'token:{key.task_auth_label}:'):
            raise ValueError(
                'task credential principal does not match provenance key'
            )
        return
    if tenant_id is None:
        raise RuntimeError('provenance key lacks a task principal binding')
