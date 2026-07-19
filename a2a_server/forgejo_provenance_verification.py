"""HMAC ownership proof for signed author session provenance."""

import hashlib
import hmac

from collections.abc import Mapping

from a2a_server.forgejo_provenance_fields import parse
from a2a_server.forgejo_provenance_keys import ProvenanceKey, resolve
from a2a_server.forgejo_provenance_payload import canonical


SHA256_HEX_LENGTH = 64


def verify(message: str, metadata: Mapping[str, object]) -> ProvenanceKey:
    """Verify provenance and bind its session to the target agent and tenant."""
    fields = parse(message)
    key = resolve(fields['CodeTether-Key-ID'])
    target = str(metadata.get('target_agent_name') or '')
    if key.agent_identity != target:
        raise ValueError('provenance key is not bound to the target agent')
    if fields['CodeTether-Agent-Identity'] != target:
        raise ValueError('provenance identity does not match the target agent')
    if fields['CodeTether-Session-ID'] != metadata.get('resume_session_id'):
        raise ValueError('provenance session does not match the author session')
    if fields['CodeTether-Provenance-ID'] != metadata.get(
        'author_provenance_id'
    ):
        raise ValueError('provenance ID does not match the author envelope')
    if fields['CodeTether-Tenant-ID'] != key.tenant_id:
        raise ValueError('provenance tenant does not match the trusted key')
    signature = fields['CodeTether-Signature']
    expected = hmac.new(key.secret.encode(), canonical(fields), hashlib.sha256)
    if len(signature) != SHA256_HEX_LENGTH or not hmac.compare_digest(
        signature, expected.hexdigest()
    ):
        raise ValueError('CodeTether provenance signature is invalid')
    return key
