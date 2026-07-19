"""Deterministic Forgejo PR conversation identity validation."""

import hashlib
import re

from collections.abc import Mapping


_REPOSITORY = re.compile(r'^[a-z0-9._-]{1,128}/[a-z0-9._-]{1,128}$')


def conversation_id(repo: str, pr_number: object, target: str) -> str:
    """Derive one reusable conversation for a repository PR and author."""
    repo = repo.lower()
    if not _REPOSITORY.fullmatch(repo):
        raise ValueError('invalid Forgejo repository identity')
    try:
        number = int(pr_number)
    except (TypeError, ValueError) as error:
        raise ValueError('invalid Forgejo PR number') from error
    if number <= 0 or str(number) != str(pr_number):
        raise ValueError('invalid Forgejo PR number')
    digest = hashlib.sha256(f'{repo}\n{number}\n{target}'.encode()).hexdigest()
    return f'forgejo_pr_{digest[:48]}'


def validate_binding(metadata: Mapping[str, object], target: str) -> None:
    """Reject aliases that disagree with the server-derived binding."""
    expected = conversation_id(
        metadata.get('repo', ''), metadata.get('pr_number'), target
    )
    if (
        metadata.get('context_id') != expected
        or metadata.get('conversation_id') != expected
    ):
        raise ValueError('conversation does not match the Forgejo PR author')
    if metadata.get('author_agent_identity') != target:
        raise ValueError('author identity alias does not match the target')
    if metadata.get('head_sha') != metadata.get('pr_head_sha'):
        raise ValueError('head SHA aliases do not match')
    login = str(metadata.get('forgejo_author_login') or '').lower()
    if str(metadata.get('git_signer') or '').lower() != f'forgejo:{login}':
        raise ValueError('verified signer does not match the Forgejo author')
