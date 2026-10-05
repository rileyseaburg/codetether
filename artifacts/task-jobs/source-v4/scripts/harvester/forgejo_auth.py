"""Obtain a scoped Forgejo review credential with the pod's Vault identity."""

import json
import os
from pathlib import Path
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    """Do not forward authentication headers to redirects."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request_json(url, *, data=None, headers=None, allow_text=False):
    headers = {
        **(headers or {}),
        'Accept': 'application/json',
        'User-Agent': 'CodeTether-ForgejoCLI/1.0',
    }
    if data is not None:
        headers['Content-Type'] = 'application/json'
    request = Request(
        url,
        data=json.dumps(data).encode() if data is not None else None,
        headers=headers,
    )
    with build_opener(NoRedirect()).open(request, timeout=25) as response:
        text = response.read().decode('utf-8')
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        if allow_text:
            return text
        raise


def credentials():
    """Use fresh Kubernetes auth, never a shared/admin VAULT_TOKEN or home file."""
    address = os.environ['VAULT_ADDR'].rstrip('/')
    mount = os.environ.get('VAULT_AUTH_MOUNT', 'kubernetes')
    role = os.environ['VAULT_ROLE']
    jwt = Path(os.environ['VAULT_K8S_SA_JWT_PATH']).read_text().strip()
    auth = request_json(
        address + '/v1/auth/' + mount + '/login',
        data={'role': role, 'jwt': jwt},
    )
    token = auth['auth']['client_token']
    path = os.environ.get(
        'FORGEJO_REVIEW_CREDENTIAL_PATH',
        'kv/data/codetether/harvester/forgejo-review',
    )
    secret = request_json(
        address + '/v1/' + path, headers={'X-Vault-Token': token}
    )['data']['data']
    # This record deliberately contains no account password or GitOps token.
    return secret['api_base'].rstrip('/'), secret['repo'], secret['token']
