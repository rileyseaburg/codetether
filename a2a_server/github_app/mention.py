"""Mention detection for GitHub App webhook comments."""

from .settings import APP_SLUG

_FIX_TERMS = (
    'fix', 'apply', 'address', 'implement', 'patch', 'rename', 'modify',
    'edit', 'refactor', 'resolve', 'cleanup', 'clean up', 'please fix',
    'make tests pass', 'make test pass', 'make build pass',
    'make ci pass', 'make lint pass', 'make this work', 'make it work',
    'make that work',
)


def mentions_bot(body: str) -> bool:
    """Return true when a comment explicitly mentions the app slug."""
    return f'@{APP_SLUG.lower()}' in (body or '').lower()


def is_fix_request(body: str) -> bool:
    """Return true when the mention clearly asks for branch changes."""
    normalized = ' '.join((body or '').lower().split())
    return mentions_bot(normalized) and any(term in normalized for term in _FIX_TERMS)
