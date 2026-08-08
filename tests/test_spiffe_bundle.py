"""Tests for verified SPIRE trust-bundle conversion."""

import json

import pytest

from a2a_server.spiffe_bundle import _pem_bundle


EXPECTED_CERTIFICATES = 2


def test_pem_bundle_extracts_only_x509_chains():
    bundle = json.dumps(
        {
            'keys': [
                {'use': 'x509-svid', 'x5c': ['first', 'second']},
                {'use': 'jwt-svid', 'kid': 'signing-key'},
            ]
        }
    )
    result = _pem_bundle(bundle)
    assert result.count('BEGIN CERTIFICATE') == EXPECTED_CERTIFICATES
    assert 'first' in result
    assert 'signing-key' not in result


def test_pem_bundle_rejects_missing_x509_roots():
    with pytest.raises(ValueError, match=r'no X.509'):
        _pem_bundle(json.dumps({'keys': [{'use': 'jwt-svid'}]}))
