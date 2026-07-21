"""Ownership validation for deterministic agent service accounts."""

from a2a_server.agent_identity_errors import IdentityConflictError


_PERSONA = 'codetether.io/persona-id'
_PROVISIONING = 'codetether.io/provisioning-id'


def verify(account: object, persona_id: str, provisioning_id: str) -> None:
    """Reject adoption of a service account from another identity request."""
    metadata = getattr(account, 'metadata', None)
    annotations = getattr(metadata, 'annotations', None) or {}
    expected = {_PERSONA: persona_id, _PROVISIONING: provisioning_id}
    if any(annotations.get(key) != value for key, value in expected.items()):
        raise IdentityConflictError(
            'Kubernetes service account belongs to another identity'
        )
