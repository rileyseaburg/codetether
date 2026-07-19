"""Fail-closed classification of Forgejo author task envelopes."""

from collections.abc import Mapping


PROTOCOL = 'codetether.forgejo-author.v1'
PROTECTED_FIELDS = (
    'resume_session_id',
    'author_provenance_id',
    'author_agent_identity',
    'provenance_verified',
    'preserve_session_workspace',
    'server_author_binding_verified',
    'author_identity_key_id',
)


def classify(metadata: Mapping[str, object]) -> bool:
    """Return true for the exact protocol or reject protected downgrade data."""
    protocol = str(metadata.get('protocol') or '')
    if protocol == PROTOCOL:
        return True
    protected = any(
        metadata.get(field) is not None for field in PROTECTED_FIELDS
    )
    forgejo_alias = protocol.startswith('codetether.forgejo-author')
    if protected or forgejo_alias:
        raise ValueError('verified author metadata requires the exact protocol')
    return False
