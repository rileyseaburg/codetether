"""Dependency carrier for webhook subpackage helpers.

Lives in the subpackage so helpers and the router can both import it without
a circular dependency. The router builds the singleton ``DEPS`` instance from
its module-bound callables and passes it to each helper.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional


@dataclass(frozen=True)
class Deps:
    """Bound callables threaded through webhook helpers as one argument."""

    installation_token: Callable[[int], Awaitable[tuple[str, Optional[str]]]]
    has_active_github_app_task: Callable[[str, int], Awaitable[bool]]
    handle_fix_request: Callable[[Any, str], Awaitable[dict[str, Any]]]
    post_issue_comment: Callable[[str, int, str, str], Awaitable[None]]
