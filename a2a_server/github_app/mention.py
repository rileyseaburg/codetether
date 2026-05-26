"""Mention detection for GitHub App webhook comments."""

from .settings import APP_SLUG

_FIX_TERMS = (
    'fix', 'apply', 'address', 'implement', 'patch', 'rename', 'modify',
    'edit', 'refactor', 'resolve', 'cleanup', 'clean up', 'please fix',
    'retry', 'continue', 'finish', 'enhance', 'improve', 'handle',
    'change', 'changes', 'update', 'follow up', 'follow-up',
    'make changes', 'make the changes', 'make follow up changes',
    'address feedback', 'address review', 'address comments',
    'requested changes', 'review changes', 'finish the feature',
    'continue the fix', 'retry this', 'make tests pass', 'make test pass',
    'make build pass', 'make ci pass', 'make lint pass', 'make this work',
    'make it work', 'make that work', 'handle this bug', 'handle this issue',
    'build failed', 'build failure', 'failing build', 'failed build',
    'check failed', 'checks failed', 'failing check', 'failing checks',
    'ci failed', 'ci failure', 'failing ci', 'tests failed', 'test failed',
    'lint failed', 'typecheck failed', 'workflow failed', 'action failed',
)


def mentions_bot(body: str) -> bool:
    """Return true when a comment explicitly mentions the app slug."""
    return f'@{APP_SLUG.lower()}' in (body or '').lower()


def is_fix_request(body: str) -> bool:
    """Return true when the mention clearly asks for branch changes."""
    normalized = ' '.join((body or '').lower().split())
    return mentions_bot(normalized) and any(term in normalized for term in _FIX_TERMS)
