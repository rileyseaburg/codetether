"""Mocked Forgejo proof transport for verification tests."""

import httpx

from tests.forgejo_metadata import commit_message, metadata


def transport(
    *,
    signer='alice',
    signer_field='username',
    head=None,
    state='open',
    signed=None,
):
    """Return PR and commit proof for one signed metadata envelope."""
    expected = 'a' * 40
    signed = signed or metadata()

    def respond(request: httpx.Request) -> httpx.Response:
        assert request.headers['authorization'] == 'token scoped-token'
        if '/pulls/' in request.url.path:
            value = {
                'state': state,
                'head': {'sha': head or expected},
                'user': {'login': 'alice'},
            }
        else:
            value = {
                'sha': expected,
                'commit': {
                    'message': commit_message(signed),
                    'verification': {
                        'verified': True,
                        'signer': {signer_field: signer},
                    },
                },
            }
        return httpx.Response(200, json=value)

    return httpx.MockTransport(respond)
