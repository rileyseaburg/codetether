"""Load rotating SPIRE X.509 trust anchors from Kubernetes."""

import json
import os
import ssl

from pathlib import Path
from urllib import request


_TOKEN_FILE = '/var/run/secrets/kubernetes.io/serviceaccount/token'
_CA_FILE = '/var/run/secrets/kubernetes.io/serviceaccount/ca.crt'


def trust_context() -> ssl.SSLContext:
    """Return system TLS trust extended with the configured SPIRE bundle."""
    context = ssl.create_default_context()
    config_map = os.getenv('SPIFFE_BUNDLE_CONFIGMAP', '').strip()
    if config_map:
        context.load_verify_locations(cadata=_load_bundle(config_map))
    return context


def _load_bundle(config_map: str) -> str:
    namespace = os.getenv('SPIFFE_BUNDLE_NAMESPACE', 'spire')
    key = os.getenv('SPIFFE_BUNDLE_KEY', 'bundle.spiffe')
    api = os.getenv(
        'SPIFFE_KUBERNETES_API_URL', 'https://kubernetes.default.svc'
    )
    token_file = os.getenv('SPIFFE_KUBERNETES_TOKEN_FILE', _TOKEN_FILE)
    ca_file = os.getenv('SPIFFE_KUBERNETES_CA_FILE', _CA_FILE)
    url = f'{api}/api/v1/namespaces/{namespace}/configmaps/{config_map}'
    token = Path(token_file).read_text().strip()
    headers = {'Authorization': f'Bearer {token}'}
    api_request = request.Request(url, headers=headers)
    api_context = ssl.create_default_context(cafile=ca_file)
    with request.urlopen(
        api_request, context=api_context, timeout=10
    ) as response:
        payload = json.load(response)
    return _pem_bundle(payload['data'][key])


def _pem_bundle(bundle: str) -> str:
    keys = json.loads(bundle)['keys']
    certificates = [cert for item in keys for cert in item.get('x5c', [])]
    if not certificates:
        raise ValueError('SPIRE bundle contains no X.509 trust anchors')
    return ''.join(
        f'-----BEGIN CERTIFICATE-----\n{cert}\n-----END CERTIFICATE-----\n'
        for cert in certificates
    )
