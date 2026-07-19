import pytest

from a2a_server.forgejo_commit_trailers import parse, verify_binding
from tests.forgejo_metadata import commit_message, metadata


def test_all_protocol_fields_are_bound_to_signed_trailers():
    value = metadata()
    verify_binding(value, commit_message(value))
    parsed = parse(commit_message(value))
    assert parsed['CodeTether-Agent-Identity'] == value['target_agent_name']


def test_changed_provenance_is_rejected():
    value = metadata()
    message = commit_message(value)
    value['author_provenance_id'] = 'ctprov_abcdef1234567890'
    with pytest.raises(ValueError, match='author_provenance_id'):
        verify_binding(value, message)


def test_duplicate_signed_trailer_is_rejected():
    value = metadata()
    message = commit_message(value) + '\nCodeTether-Agent-Slot: other\n'
    with pytest.raises(ValueError, match='ambiguous'):
        parse(message)
