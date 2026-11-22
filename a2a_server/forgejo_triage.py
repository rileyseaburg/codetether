"""Let the coding agent triage an issue against open work before changing code.

Rudder files many issues for one defect, and some log lines are benign. The
server gives the agent the open pull requests and issues most similar to the
task's issue; the agent ends its reply with one verdict line:

    CODETETHER_TRIAGE: proceed
    CODETETHER_TRIAGE: duplicate #<open PR or issue number>
    CODETETHER_TRIAGE: not_needed <one-line reason>

Duplicate and not-needed verdicts close the issue with an explanation instead
of opening review on a branch with no changes.
"""

import re

from collections.abc import Awaitable, Callable
from typing import Any

from a2a_server.forgejo_related_pr import family_tokens


MAX_PAGES = 4
PAGE_SIZE = 50
MAX_CANDIDATES = 15
_VERDICT = re.compile(
    r'^\s*CODETETHER_TRIAGE:\s*(proceed|duplicate|not_needed)\b\s*(.*)$',
    re.IGNORECASE | re.MULTILINE,
)
_NUMBER = re.compile(r'#(\d+)')

Api = Callable[..., Awaitable[Any]]


def _similarity(left: str, right: str) -> float:
    a, b = set(family_tokens(left)), set(family_tokens(right))
    return len(a & b) / len(a | b) if a and b else 0.0


async def _open_items(api: Api, base: str, path: str, kind: str) -> list[dict]:
    rows: list[dict] = []
    query = (
        'pulls?state=open' if kind == 'pr' else 'issues?state=open&type=issues'
    )
    for page in range(1, MAX_PAGES + 1):
        batch = await api(
            'GET', base, f'{path}/{query}&limit={PAGE_SIZE}&page={page}'
        )
        if not isinstance(batch, list):
            break
        rows.extend({**row, '_kind': kind} for row in batch)
        if len(batch) < PAGE_SIZE:
            break
    return rows


async def similar_open_work(
    api: Api, base: str, path: str, number: int, title: str
) -> list[dict]:
    """Return the open PRs and issues most similar to issue `number`."""
    items = await _open_items(api, base, path, 'pr')
    items += await _open_items(api, base, path, 'issue')
    scored = [
        (_similarity(title, str(item.get('title') or '')), item)
        for item in items
        if int(item.get('number') or 0) != number
    ]
    scored = [pair for pair in scored if pair[0] > 0]
    scored.sort(key=lambda pair: (-pair[0], int(pair[1].get('number') or 0)))
    return [item for _, item in scored[:MAX_CANDIDATES]]


def triage_instructions(number: int, candidates: list[dict]) -> str:
    """Prompt preamble listing similar open work and the verdict contract."""
    lines = []
    for item in candidates:
        head = (item.get('head') or {}).get('ref') or ''
        branch = f' (branch `{head}`)' if head else ''
        kind = 'PR' if item['_kind'] == 'pr' else 'Issue'
        title = str(item.get('title') or '')[:160]
        lines.append(f'- {kind} #{item["number"]}{branch}: {title}')
    listing = '\n'.join(lines) or '- (no similar open pull requests or issues)'
    return (
        f'Triage before changing code. Issue #{number} may duplicate open '
        'work or describe a log line that is not a defect.\n\n'
        'Most similar open pull requests and issues in this repository:\n'
        f'{listing}\n\n'
        'Decide first, using the issue evidence, these items, and the code:\n'
        '- duplicate: an open PR or issue above already covers this same '
        'defect. Do not change code.\n'
        '- not_needed: the evidence is benign or expected behaviour (for '
        'example an informational or zero-failure report logged at error '
        'level) and no change is warranted. Do not change code.\n'
        '- proceed: real, uncovered work. Implement it as instructed below.'
        '\n\n'
        'End your final reply with exactly one line, for example:\n'
        'CODETETHER_TRIAGE: proceed\n'
        'CODETETHER_TRIAGE: duplicate #<number>\n'
        'CODETETHER_TRIAGE: not_needed <one-line reason>\n\n'
    )


def parse_triage(result: str) -> tuple[str, int, str]:
    r"""Return (verdict, referenced number, reason) from the last verdict line.

    A missing or malformed verdict is `proceed`, so existing behaviour holds.

    >>> parse_triage('done\nCODETETHER_TRIAGE: duplicate #6878')
    ('duplicate', 6878, '#6878')
    """
    matches = list(_VERDICT.finditer(result or ''))
    if not matches:
        return 'proceed', 0, ''
    verdict, rest = matches[-1].group(1).lower(), matches[-1].group(2).strip()
    number = _NUMBER.search(rest)
    if verdict == 'duplicate' and not number:
        return 'proceed', 0, rest
    return verdict, int(number.group(1)) if number else 0, rest[:300]
