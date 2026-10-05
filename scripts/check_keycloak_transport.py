"""Read-only discovery check, intended to run inside an API pod. No credentials."""

import base64
import json
import os
import sys
import httpx


def main():
    origin = os.environ['KEYCLOAK_URL'].rstrip('/')
    if '--compare-internal' in sys.argv:
        origin = 'http://keycloak.keycloak.svc.cluster.local:8080'
    realm = os.environ['KEYCLOAK_REALM']
    expected = os.environ['KEYCLOAK_ISSUER'].rstrip('/')
    url = f'{origin}/realms/{realm}/.well-known/openid-configuration'
    with httpx.Client(timeout=15) as client:
        response = client.get(url)
        print(json.dumps({'status': response.status_code,
                          'server': response.headers.get('server')}))
        response.raise_for_status()
        discovery = response.json()
    actual = discovery.get('issuer')
    report = {
        'transport': origin,
        'expected_issuer': expected,
        'discovery_issuer': actual,
        'matches': actual == expected,
    }
    print(json.dumps(report))
    if actual != expected:
        raise SystemExit('Issuer mismatch')
    client_id = os.environ.get('KEYCLOAK_PROVISIONER_CLIENT_ID')
    client_secret = os.environ.get('KEYCLOAK_PROVISIONER_CLIENT_SECRET')
    if client_id and client_secret:
        token_realm = os.environ.get('KEYCLOAK_PROVISIONER_REALM', realm)
        with httpx.Client(timeout=15) as client:
            response = client.post(
                f'{origin}/realms/{token_realm}/protocol/openid-connect/token',
                data={'grant_type': 'client_credentials', 'client_id': client_id,
                      'client_secret': client_secret},
            )
            response.raise_for_status()
            encoded = response.json()['access_token'].split('.')[1]
            claims = json.loads(base64.urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4)))
        print(json.dumps({'token_status': response.status_code,
                          'observed_token_issuer': claims.get('iss'),
                          'issuer_matches': claims.get('iss') == expected,
                          'user_login_attempted': False}))
        if claims.get('iss') != expected:
            raise SystemExit('Token issuer mismatch')

if __name__ == '__main__':
    main()