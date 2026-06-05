"""Installation and repository-scope webhook handling.

The GitHub App emits ``installation`` (action=created) and
``installation_repositories`` (action=added|created) when the install scope
changes. We do not auto-dispatch work in response; we log the scope change
and return a guidance body the operator can use to activate specific repos.
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Optional

from ..settings import APP_SLUG
from . import responses

TokenMint = Callable[[int], Awaitable[tuple[str, Optional[str]]]]

logger = logging.getLogger(__name__)

WELCOME_BODY = (
    "## 🤖 CodeTether\n\n"
    "Thanks for installing CodeTether. I only act on explicit "
    f"`@{APP_SLUG}` mentions on issues and pull requests, so I will not "
    "start work on open items in this repository automatically.\n\n"
    "To enable active-work scanning for a specific repository, add a "
    "`codetether.active` label to that repository, or check in a "
    "`.github/codetether.yml` file with:\n\n"
    "```yaml\n"
    "active: true\n"
    "```\n\n"
    "For one-off work, leave a comment starting with "
    f"`@{APP_SLUG} handle this` or `@{APP_SLUG} fix this` on an issue or PR."
)


def _repos_added(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the list of repository dicts added to the installation scope."""
    repos = payload.get('repositories_added')
    if isinstance(repos, list):
        return repos
    repos = payload.get('repositories')
    return repos if isinstance(repos, list) else []


def _record_welcome(repo: dict[str, Any], installation_id: int) -> str | None:
    """Record a welcome event for a single newly-scoped repo."""
    full_name = str(repo.get('full_name') or '').strip()
    if not full_name:
        return None
    logger.info(
        'GitHub App installation scope added repo: installation=%s repo=%s',
        installation_id,
        full_name,
    )
    return full_name


async def handle_installation_scope_event(
    event_name: str,
    payload: dict[str, Any],
    *,
    installation_token: TokenMint,
) -> dict[str, Any]:
    """Acknowledge a new installation or repo-scope addition with guidance."""
    installation_id = int(payload.get('installation', {}).get('id') or 0)
    if not installation_id:
        return responses.ignored(event_name, 'missing-installation-id')
    await installation_token(installation_id)
    welcomed: list[str] = []
    for repo in _repos_added(payload):
        name = _record_welcome(repo, installation_id)
        if name:
            welcomed.append(name)
    return responses.accepted(
        event_name,
        installation_id=installation_id,
        welcomed_repos= welcomed,
        guidance=WELCOME_BODY,
    )
