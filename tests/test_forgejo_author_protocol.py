import pytest

from a2a_server.forgejo_author_contract import validate
from a2a_server.forgejo_author_identity import canonical_identity
from a2a_server.forgejo_author_task import task_identity
from tests.forgejo_metadata import metadata


def test_identity_matches_cross_runtime_contract_vector():
    assert canonical_identity('forge.example', 'alice', 'default') == (
        'ctforgejo_9e1fbe45a595b21bd9146db4a011cae0de38f193'
    )


def test_identity_is_principal_bound():
    value = metadata()
    assert validate(value) == value['target_agent_name']
    value['target_agent_name'] = canonical_identity(
        'forge.example', 'mallory', 'default'
    )
    with pytest.raises(ValueError, match='target'):
        validate(value)


def test_task_id_is_deterministic_across_callers():
    first = task_identity(metadata())
    second = task_identity(dict(metadata()))
    assert first == second
    assert first[1].startswith('cttask_')


def test_new_head_creates_new_logical_task():
    first = metadata()
    second = metadata()
    second['pr_head_sha'] = 'b' * 40
    second['head_sha'] = 'b' * 40
    assert task_identity(first) != task_identity(second)
