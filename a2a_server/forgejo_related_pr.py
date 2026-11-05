"""Find an open CodeTether PR that already addresses the same issue family.

Rudder files a new issue for every log line whose numbers differ (scores,
counts, IDs), so many issues describe one defect. Each used to get its own
`codetether/issue-N` branch and PR, which conflict with each other and never
converge on a passing PR. Issue work now continues the oldest matching open
PR instead of opening another one.
"""

import re

from collections.abc import Awaitable, Callable
from typing import Any


BRANCH_PREFIX = 'codetether/issue-'
PAGE_SIZE = 50
MAX_PAGES = 20
KEY_TOKENS = 8
MIN_TOKENS = 4

_PR_PREFIX = re.compile(r'^\s*fix\s+#\d+:\s*', re.IGNORECASE)
_LOG_PREFIX = re.compile(r'^\s*\[[a-z]+\]\s+[\w.-]+:\s*', re.IGNORECASE)
_WORD = re.compile(r'[a-z]+')
# Structured-log keys and placeholders carry no defect identity.
_NOISE = frozenset(
    {
        'error',
        'warn',
        'warning',
        'info',
        'level',
        'severity',
        'timestamp',
        'ti',
        'num',
        'message',
        'msg',
        'target',
        'span',
        'spans',
        'name',
        'id',
    }
)

Api = Callable[..., Awaitable[Any]]


def family_tokens(title: str) -> list[str]:
    """Return the identity words of an issue or `Fix #N:` PR title.

    Numbers, punctuation, pass/fail marks and log-field names are removed so
    `Brand: ✓ (85)` and `Brand: ✗ (50)` describe the same family.

    >>> family_tokens('[ERROR] app: [FullAudit] Combined result: FAILED - x 1')
    ['fullaudit', 'combined', 'result', 'failed', 'x']
    """
    text = _LOG_PREFIX.sub('', _PR_PREFIX.sub('', title or ''), count=1)
    words = _WORD.findall(text.lower())
    return [word for word in words if word not in _NOISE]


def same_family(left: str, right: str) -> bool:
    """Whether two titles share a specific (not generic) identity prefix."""
    a, b = family_tokens(left), family_tokens(right)
    size = min(KEY_TOKENS, len(a), len(b))
    return size >= MIN_TOKENS and a[:size] == b[:size]


def _issue_number(branch: str) -> int:
    suffix = branch[len(BRANCH_PREFIX) :]
    return int(suffix) if suffix.isdigit() else 0


async def find_related_pr(
    api: Api, base: str, path: str, number: int, title: str
) -> dict[str, Any] | None:
    """Return the oldest open CodeTether PR for this issue's family.

    Returns `None` when this issue already owns a PR (normal branch reuse
    applies), when the title is too generic to match safely, or when no
    automation PR matches. Human-authored branches are never adopted.
    """
    if len(family_tokens(title)) < MIN_TOKENS:
        return None
    own = f'{BRANCH_PREFIX}{number}'
    matches = []
    for page in range(1, MAX_PAGES + 1):
        rows = await api(
            'GET',
            base,
            f'{path}/pulls?state=open&limit={PAGE_SIZE}&page={page}',
        )
        if not isinstance(rows, list):
            raise RuntimeError('Forgejo PR listing unavailable')
        for row in rows:
            head = row.get('head') or {}
            ref = str(head.get('ref') or '')
            if ref == own:
                return None
            if not ref.startswith(BRANCH_PREFIX) or not _issue_number(ref):
                continue
            if same_family(title, str(row.get('title') or '')):
                matches.append(row)
        if len(rows) < PAGE_SIZE:
            break
    if not matches:
        return None
    row = min(matches, key=lambda item: int(item.get('number') or 0))
    head = row.get('head') or {}
    return {
        'number': int(row['number']),
        'branch': str(head.get('ref') or ''),
        'head_sha': str(head.get('sha') or ''),
        'issue_number': _issue_number(str(head.get('ref') or '')),
        'html_url': str(row.get('html_url') or ''),
    }


def related_instructions(related: dict[str, Any], number: int) -> str:
    """Prompt text telling the agent to finish the existing PR."""
    pr = related['number']
    branch = related['branch']
    return (
        f'\n\nIssue #{number} is the same defect family as open PR #{pr} '
        f'(`{branch}`, originally for issue '
        f'#{related.get("issue_number") or "?"}). Do not create a new '
        'branch or pull request. Work on '
        f'`{branch}`: confirm whether PR #{pr} already resolves the evidence '
        f'in issue #{number}, extend it only where it does not, then make '
        f'PR #{pr} pass. Inspect its failing commit statuses and Forgejo '
        'Actions logs, fix the causes on the branch, and push to '
        f'`{branch}` through the repository hooks. Add `Refs #{number}` to '
        'the commit message. Report the PR number, pushed SHA, and which '
        'checks are still failing or pending.'
    )
