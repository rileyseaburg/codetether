import pytest

from a2a_server.forgejo_author_contract import validate
from a2a_server.forgejo_conversation_identity import conversation_id
from tests.forgejo_metadata import metadata


def test_conversation_is_stable_across_head_revisions():
    first = metadata()
    second = metadata()
    second['pr_head_sha'] = 'b' * 40
    second['head_sha'] = 'b' * 40
    assert first['context_id'] == second['context_id']
    assert validate(first) == validate(second)


def test_conversation_is_scoped_to_repository_pr_and_author():
    target = metadata()['target_agent_name']
    first = conversation_id('owner/repo', 42, target)
    assert first != conversation_id('owner/other', 42, target)
    assert first != conversation_id('owner/repo', 43, target)
    assert first.startswith('forgejo_pr_')


@pytest.mark.parametrize(
    ('field', 'value'),
    [
        ('context_id', 'attacker-selected'),
        ('conversation_id', 'attacker-selected'),
        ('author_agent_identity', 'ctforgejo_attacker'),
        ('head_sha', 'b' * 40),
        ('git_signer', 'forgejo:mallory'),
    ],
)
def test_binding_aliases_fail_closed(field, value):
    item = metadata()
    item[field] = value
    with pytest.raises(ValueError):
        validate(item)


@pytest.mark.parametrize('field', ['resume_session_id', 'author_provenance_id'])
def test_required_signed_continuity_fields_fail_closed(field):
    value = metadata()
    value[field] = ''
    with pytest.raises(ValueError):
        validate(value)
