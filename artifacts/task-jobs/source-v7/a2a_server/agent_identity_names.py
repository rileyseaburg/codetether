"""Deterministic workload names for persona identity instances."""

import hashlib
import os
import re

from a2a_server.agent_identity_errors import IdentityConfigurationError
from a2a_server.agent_identity_types import WorkloadIdentity


def workload_identity(
    provisioning_id: str, persona_id: str
) -> WorkloadIdentity:
    """Derive stable Kubernetes, Keycloak, Forgejo, and SPIFFE identifiers."""
    digest = hashlib.sha256(provisioning_id.encode()).hexdigest()[:10]
    persona = _slug(persona_id)
    service_account = f'ct-agent-{persona[:34]}-{digest}'
    username = f'ct-{persona[:24]}-{digest}'
    namespace = os.environ.get('AGENT_IDENTITY_NAMESPACE') or os.environ.get(
        'KUBERNETES_NAMESPACE', 'a2a-server'
    )
    trust_domain = os.environ.get('SPIFFE_TRUST_DOMAIN', '').strip().lower()
    if not re.fullmatch(r'[a-z0-9.-]+', trust_domain):
        raise IdentityConfigurationError(
            'SPIFFE_TRUST_DOMAIN is not configured'
        )
    spiffe_id = f'spiffe://{trust_domain}/ns/{namespace}/sa/{service_account}'
    return WorkloadIdentity(
        namespace,
        service_account,
        service_account,
        username,
        f'{username}@agents.invalid',
        spiffe_id,
    )


def _slug(value: str) -> str:
    slug = re.sub(r'[^a-z0-9]+', '-', value.lower()).strip('-')
    if not slug:
        raise ValueError('persona_id must contain an alphanumeric character')
    return slug
