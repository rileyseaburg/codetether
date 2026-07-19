import json

import pytest

from a2a_server.forgejo_author_verification import verify
from tests.forgejo_metadata import metadata
from tests.forgejo_provenance_fixture import registry
from tests.forgejo_verification_transport import transport


@pytest.fixture(autouse=True)
def configured_host(monkeypatch):
    value = {'forge.example': 'https://forge.example/api/v1'}
    monkeypatch.setenv('CODETETHER_FORGEJO_API_BASE_URLS', json.dumps(value))
    monkeypatch.setenv(
        'CODETETHER_PROVENANCE_SIGNING_KEYS', registry(metadata())
    )
    monkeypatch.setenv(
        'CODETETHER_PROVENANCE_SIGNING_KEYS', registry(metadata())
    )


@pytest.mark.asyncio
async def test_server_independently_verifies_pr_signer_and_trailers():
    await verify(metadata(), 'scoped-token', transport())


@pytest.mark.asyncio
async def test_server_accepts_forgejo_login_signer_alias():
    await verify(metadata(), 'scoped-token', transport(signer_field='login'))


@pytest.mark.asyncio
@pytest.mark.parametrize('change', ['signer', 'head', 'state'])
async def test_server_rejects_stale_or_unverified_proof(change):
    kwargs = {
        change: {'signer': 'mallory', 'head': 'b' * 40, 'state': 'closed'}[
            change
        ]
    }
    with pytest.raises((ValueError, LookupError)):
        await verify(metadata(), 'scoped-token', transport(**kwargs))


@pytest.mark.asyncio
async def test_server_rejects_metadata_not_present_in_signed_commit():
    signed, forwarded = metadata(), metadata()
    forwarded['author_provenance_id'] = 'ctprov_abcdef1234567890'
    with pytest.raises(ValueError, match='author_provenance_id'):
        await verify(forwarded, 'scoped-token', transport(signed=signed))


@pytest.mark.asyncio
async def test_server_requires_a_non_persisted_verification_token():
    with pytest.raises(RuntimeError, match='credential'):
        await verify(metadata(), '', transport())
