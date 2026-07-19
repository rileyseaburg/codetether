import pytest

from a2a_server.forgejo_task_authorization import require
from tests.forgejo_service_fixture import provenance_key


def test_author_key_accepts_only_its_configured_task_principal():
    require(provenance_key(), 'token:reviewer:credential-hash', None)
    with pytest.raises(ValueError, match='principal'):
        require(provenance_key(), 'token:attacker:credential-hash', None)


def test_policy_tenant_must_match_the_author_key():
    require(provenance_key(), 'tenant:tenant', 'tenant')
    with pytest.raises(ValueError, match='tenant'):
        require(provenance_key(), 'tenant:other', 'other')
