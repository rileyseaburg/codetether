"""Shared valid metadata for Forgejo author protocol tests."""

from a2a_server.forgejo_author_identity import canonical_identity
from a2a_server.forgejo_conversation_identity import conversation_id
from tests.forgejo_provenance_fixture import signed_message


def metadata() -> dict[str, object]:
    """Build one complete, internally consistent protocol envelope."""
    target = canonical_identity('forge.example', 'alice', 'default')
    context = conversation_id('owner/repo', 42, target)
    return {
        'protocol': 'codetether.forgejo-author.v1',
        'source': 'forgejo-pr-review',
        'workflow_stage': 'forgejo-author-review',
        'forgejo_host': 'forge.example',
        'forgejo_author_login': 'alice',
        'agent_slot': 'default',
        'target_agent_name': target,
        'repo': 'owner/repo',
        'pr_number': 42,
        'pr_head_sha': 'a' * 40,
        'resume_session_id': 'author-session',
        'author_provenance_id': 'ctprov_1234567890abcdef',
        'provenance_verified': True,
        'preserve_session_workspace': True,
        'author_agent_identity': target,
        'head_sha': 'a' * 40,
        'git_signer': 'forgejo:alice',
        'context_id': context,
        'conversation_id': context,
    }


def commit_message(value: dict[str, object]) -> str:
    """Build the signed trailer block for a valid envelope."""
    return signed_message(value)
