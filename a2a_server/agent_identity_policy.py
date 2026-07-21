"""OPA authority validation and immutable policy receipt generation."""

import hashlib
import json

from a2a_server.agent_identity_claims import data


def policy_revision() -> str:
    """Return a content-addressed revision for the active local role catalog."""
    encoded = json.dumps(data(), sort_keys=True, separators=(',', ':')).encode()
    return f'sha256:{hashlib.sha256(encoded).hexdigest()}'


def policy_binding(spiffe_id: str, subject: str) -> str:
    """Identify the durable bridge from SPIFFE authentication to authority."""
    digest = hashlib.sha256(f'{spiffe_id}:{subject}'.encode()).hexdigest()
    return f'spiffe-keycloak:sha256:{digest}'
