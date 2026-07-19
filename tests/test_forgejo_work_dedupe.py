# ruff: noqa: SLF001
"""Forgejo work stays outside the generic GitHub App dedupe path."""

from a2a_server import persistent_worker_pool as pool


def test_forgejo_review_uses_the_dedicated_protocol_boundary():
    metadata = {
        'source': 'forgejo-pr-review',
        'repo': 'owner/repo',
        'pr_number': 7,
        'workflow_stage': 'forgejo-author-review',
        'pr_head_sha': 'abc123',
    }
    assert pool._github_work_key(metadata) is None
