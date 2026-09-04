"""Mention detection for GitHub App and Forgejo webhook comments.

Forgejo hosts more than one bot identity (`@codetether`, `@codetether-bot`), and
operators type whichever they see on the issue. Substring matching also made
`@codetether-bot` match the `@codetether` slug by accident, which left the
trailing `-bot` in the text that `is_fix_request` inspected.

Aliases are matched on word boundaries so `@codetether-bot handle this` is
recognized as a mention of the bot and nothing else.
"""

from __future__ import annotations

import os
import re

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
    # Plain assignment language. Operators say "work on this" or "take this"
    # far more often than any of the verbs above; without these the bot
    # answered "ask me explicitly" to a clearly explicit request.
    'work on', 'take this', 'take it', 'take care', 'pick this up',
    'pick it up', 'do this', 'do it', 'get this done', 'get it done',
    'look into', 'investigate', 'build this', 'build it', 'ship this',
    'ship it', 'tackle', 'solve', 'complete this', 'complete it',
    'start on', 'go ahead', 'proceed', 'you\'re up', 'your turn',
    'assign', 'assigned to you', 'own this', 'knock this out',
)

# Bot identities that exist on the Forgejo instance today. `CODETETHER_BOT_ALIASES`
# accepts a comma-separated list so a new identity does not require a code change.
_DEFAULT_ALIASES = ('codetether', 'codetether-bot', 'codetether-agent')


def bot_aliases() -> tuple[str, ...]:
    """Return every handle that counts as addressing the agent.

    The configured `APP_SLUG` is always included so existing deployments keep
    working. Longer aliases are returned first so `@codetether-bot` is stripped
    before the shorter `@codetether` prefix can match it.
    """
    configured = os.environ.get('CODETETHER_BOT_ALIASES', '')
    names = {
        alias.strip().lstrip('@').lower()
        for alias in (*_DEFAULT_ALIASES, *configured.split(','))
        if alias.strip()
    }
    names.add(APP_SLUG.strip().lstrip('@').lower())
    return tuple(sorted((name for name in names if name), key=len, reverse=True))


def _mention_pattern() -> re.Pattern[str]:
    alternatives = '|'.join(re.escape(alias) for alias in bot_aliases())
    # A mention ends at a boundary that is not a name character, so
    # `@codetether-bot` cannot be matched by the shorter `codetether` alias.
    return re.compile(rf'(?<![\w/-])@({alternatives})(?![\w-])', re.IGNORECASE)


def mentions_bot(body: str) -> bool:
    """Return true when the text explicitly mentions one of the bot handles."""
    return _mention_pattern().search(body or '') is not None


def strip_mentions(body: str) -> str:
    """Remove bot mentions so intent parsing sees only the request text."""
    return _mention_pattern().sub(' ', body or '')


def is_fix_request(body: str) -> bool:
    """Return true when the mention clearly asks for branch changes."""
    if not mentions_bot(body):
        return False
    normalized = ' '.join(strip_mentions(body).lower().split())
    return any(term in normalized for term in _FIX_TERMS)
