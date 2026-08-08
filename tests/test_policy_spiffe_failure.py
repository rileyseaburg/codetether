"""Fail-closed tests for policy SPIFFE token resolution."""

import pytest

from fastapi import HTTPException
from jwt import encode

import a2a_server.policy_spiffe_resolver as resolver


@pytest.mark.asyncio
async def test_invalid_spiffe_candidate_fails_closed(monkeypatch):
    monkeypatch.setattr(resolver.spiffe_auth, 'spiffe_enabled', lambda: True)

    def invalid(_):
        raise HTTPException(status_code=401, detail='invalid SVID')

    monkeypatch.setattr(resolver.spiffe_auth, 'validate_jwt_svid', invalid)
    token = encode({'sub': 'spiffe://td/ns/a/sa/b'}, 'bad', algorithm='HS256')
    with pytest.raises(HTTPException, match='invalid SVID'):
        await resolver.resolve(token)
