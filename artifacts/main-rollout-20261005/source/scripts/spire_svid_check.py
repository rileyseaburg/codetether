"""Validate a real SPIRE-minted JWT-SVID with the local validator.

Usage (from repo root; see artifacts/ui-audit/spire-svid-check.txt for the
full mint command):
    SVID=$(kubectl -n spire exec spire-server-0 -c spire-server -- \
        /opt/spire/bin/spire-server jwt mint -audience a2a-server \
        -spiffeID <worker SPIFFE ID> -ttl 60s)
    SVID="$SVID" venv/bin/python scripts/spire_svid_check.py

Uses the live SPIRE JWT bundle as the JWKS (same keys the OIDC discovery
provider serves), and the production trust domain / issuer / audience.
Prints only claim metadata, never the token.
"""

import json
import os
import sys

from pathlib import Path

from jwt import PyJWK, PyJWKSet, get_unverified_header

from a2a_server import spiffe_auth
from a2a_server.policy_middleware import worker_identity_allowed


BUNDLE = Path('artifacts/ui-audit/spire-bundle.json')
WORKER = 'spiffe://codetether.io/ns/a2a-system/sa/a2a-server-harvester'


class _BundleClient:
    def __init__(self, bundle: dict) -> None:
        keys = [k for k in bundle['keys'] if k.get('use') == 'jwt-svid']
        self._set = PyJWKSet.from_dict({'keys': keys})

    def get_signing_key_from_jwt(self, token: str) -> PyJWK:
        kid = get_unverified_header(token)['kid']
        return next(k for k in self._set.keys if k.key_id == kid)


def main() -> int:
    """Validate $SVID and print only identity metadata."""
    os.environ.update(
        {
            'SPIFFE_ENABLED': 'true',
            'SPIFFE_TRUST_DOMAIN': 'codetether.io',
            'SPIFFE_ISSUER': 'https://oidc-discovery.codetether.io',
            'SPIFFE_AUDIENCE': 'a2a-server',
            'SPIFFE_WORKER_IDS': WORKER,
        }
    )
    client = _BundleClient(json.loads(BUNDLE.read_text()))
    spiffe_auth._get_jwk_client = lambda: client  # noqa: SLF001
    token = os.environ['SVID'].strip()
    identity = spiffe_auth.validate_jwt_svid(token)
    user = identity.to_policy_user()
    print(f'validated spiffe_id={identity.spiffe_id}')
    print(f'worker_allowed={worker_identity_allowed(user)}')
    os.environ['SPIFFE_TRUST_DOMAIN'] = 'codetether.run'
    try:
        spiffe_auth.validate_jwt_svid(token)
    except Exception as exc:
        code = getattr(exc, 'status_code', '?')
        print(f'old_trust_domain_codetether.run -> rejected {code}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
