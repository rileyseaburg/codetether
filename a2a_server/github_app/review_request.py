"""GitHub reviewer request helpers for CodeTether App workflows."""

from __future__ import annotations

import logging

from .auth import github_json
from .settings import APP_SLUG

logger = logging.getLogger(__name__)


def is_human_reviewer_login(login: str | None) -> bool:
    """Return true when ``login`` is safe to request as a human reviewer.

    GitHub App installation tokens author PRs/comments as ``<app-slug>[bot]`` and
    GitHub does not let that bot approve its own PRs.  We therefore only request
    review from the human who triggered the workflow, never from the App/bots.
    """
    normalized = str(login or '').strip()
    if not normalized:
        return False
    lowered = normalized.lower()
    app_slug = APP_SLUG.lower()
    if lowered == f'{app_slug}[bot]' or lowered.startswith(app_slug):
        return False
    if lowered.endswith('[bot]'):
        return False
    return True


async def request_human_review(
    repo: str,
    pr_number: int,
    token: str,
    reviewer_login: str | None,
) -> bool:
    """Request PR review from the triggering human, if one is known.

    Returns ``True`` when GitHub accepted the reviewer request.  Failures are
    logged and swallowed so review automation still continues when the user is
    not a collaborator or the installation lacks reviewer-request permission.
    """
    if not is_human_reviewer_login(reviewer_login):
        return False

    reviewer = str(reviewer_login).strip()
    try:
        await github_json(
            'POST',
            f'/repos/{repo}/pulls/{int(pr_number)}/requested_reviewers',
            token,
            {'reviewers': [reviewer]},
        )
        logger.info('Requested GitHub review from @%s on %s#%s', reviewer, repo, pr_number)
        return True
    except Exception as exc:  # pragma: no cover - network/API failure path
        logger.warning(
            'Could not request GitHub review from @%s on %s#%s: %s',
            reviewer,
            repo,
            pr_number,
            exc,
        )
        return False
