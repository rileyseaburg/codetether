import pytest

from a2a_server.agent_identity_claims import normalize
from a2a_server.agent_identity_policy import policy_revision


def test_persona_authority_is_explicit_and_normalized():
    roles, groups = normalize(['line-manager', 'line-manager'], ['Engineering'])
    assert roles == ['line-manager']
    assert groups == ['engineering']
    assert policy_revision().startswith('sha256:')


@pytest.mark.parametrize('role', ['admin', 'a2a-admin', 'made-up-manager'])
def test_persona_cannot_self_grant_privileged_or_unknown_role(role):
    with pytest.raises(ValueError):
        normalize([role], ['engineering'])
