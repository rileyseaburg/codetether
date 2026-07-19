"""Public response projection for Forgejo author tasks."""

from collections.abc import Mapping


PROTOCOL = 'codetether.forgejo-author.v1'
SENSITIVE = {
    'resume_session_id',
    'author_provenance_id',
    'author_agent_identity',
    'target_worker_id',
    'author_identity_key_id',
    'server_author_binding_verified',
    'tenant_id',
    'idempotency_key',
    'github_work_key',
    'context_id',
    'conversation_id',
}


def public(task: Mapping[str, object]) -> dict[str, object]:
    """Remove private continuation capabilities from a public task response."""
    result = dict(task)
    metadata = result.get('metadata')
    if not isinstance(metadata, dict) or metadata.get('protocol') != PROTOCOL:
        return result
    result['metadata'] = {
        key: value for key, value in metadata.items() if key not in SENSITIVE
    }
    result['session_id'] = None
    return result
