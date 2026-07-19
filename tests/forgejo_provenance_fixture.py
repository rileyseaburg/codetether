"""Cryptographically signed CodeTether provenance fixtures."""

import hashlib
import hmac
import json

from a2a_server.forgejo_provenance_payload import canonical

KEY_ID = 'author-key'
SECRET = 'test-provenance-secret'
TENANT = 'tenant'


def registry(value: dict[str, object]) -> str:
    """Return server key configuration bound to the fixture author."""
    binding = {
        'secret': SECRET,
        'agent_identity': value['author_agent_identity'],
        'tenant_id': TENANT,
        'task_auth_label': 'reviewer',
    }
    return json.dumps({KEY_ID: binding})


def signed_message(value: dict[str, object]) -> str:
    """Build a commit message signed with the Rust-compatible HMAC payload."""
    fields = {
        'CodeTether-Provenance-ID': str(value['author_provenance_id']),
        'CodeTether-Session-ID': str(value['resume_session_id']),
        'CodeTether-Tenant-ID': TENANT,
        'CodeTether-Agent-Identity': str(value['author_agent_identity']),
        'CodeTether-Agent-Name': 'author',
        'CodeTether-Origin': 'worker',
        'CodeTether-Key-ID': KEY_ID,
        'CodeTether-Forgejo-Host': str(value['forgejo_host']),
        'CodeTether-Forgejo-Login': str(value['forgejo_author_login']),
        'CodeTether-Agent-Slot': str(value['agent_slot']),
    }
    signature = hmac.new(SECRET.encode(), canonical(fields), hashlib.sha256)
    fields['CodeTether-Signature'] = signature.hexdigest()
    trailers = [f'{label}: {field}' for label, field in fields.items()]
    return '\n'.join(['Signed author commit', '', *trailers])
