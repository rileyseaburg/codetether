"""Failed-check remediation loop for GitHub App webhooks.

Normalizes ``check_run``, ``check_suite``, and ``workflow_run`` webhook events
into a single :class:`RemediationContext` and queues at most one idempotent
remediation task per failing check name + head SHA combination.

Key design goals:
- **Recursion prevention:** CodeTether-authored checks (by slug, name prefix,
  or app ID) are silently ignored.
- **Idempotency:** Repeated GitHub deliveries or re-rerun events do not spawn
  duplicate tasks.  A Redis-backed (or in-process) dedup key is used.
- **Actionable worker prompt:** The resulting task instructs the agent to fetch
  logs, patch the branch, push a commit, and comment with evidence — no merge.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from .settings import APP_SLUG

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal context
# ---------------------------------------------------------------------------

_FAILED_CONCLUSIONS = frozenset({
    'failure', 'timed_out', 'cancelled', 'action_required',
})

_CODETETHER_CHECK_PREFIXES: tuple[str, ...] = (
    'CodeTether',
    'codetether',
    f'{APP_SLUG}',
)

# In-process idempotency set.  In production the caller should also use
# a database / Redis uniqueness constraint; this set prevents duplicate
# tasks within a single process lifetime and is sufficient for tests.
_seen_dedup_keys: set[str] = set()


@dataclass(slots=True)
class RemediationContext:
    """Normalized representation of a failed GitHub check event."""

    repo_full_name: str
    installation_id: int
    head_sha: str
    check_name: str
    conclusion: str
    details_url: str
    event_type: str  # 'check_run' | 'check_suite' | 'workflow_run'
    pr_number: int | None = None
    branch: str = ''
    app_slug: str | None = None
    app_id: int | None = None

    @property
    def dedup_key(self) -> str:
        """Stable idempotency key: ``<repo>:<check_name>:<head_sha>``."""
        raw = f'{self.repo_full_name}:{self.check_name}:{self.head_sha}'
        return hashlib.sha256(raw.encode()).hexdigest()[:40]


def _is_codetether_authored(ctx: RemediationContext) -> bool:
    """Return *True* when the check was created by the CodeTether GitHub App."""
    slug_lower = APP_SLUG.lower()
    # Match by app slug / name prefix
    if ctx.app_slug and ctx.app_slug.lower().startswith(slug_lower):
        return True
    # Match check name prefix (CodeTether / <slug>)
    name_lower = (ctx.check_name or '').lower()
    for prefix in _CODETETHER_CHECK_PREFIXES:
        if name_lower.startswith(prefix.lower()):
            return True
    return False


# ---------------------------------------------------------------------------
# Payload normalizers
# ---------------------------------------------------------------------------

def parse_check_run(payload: dict[str, Any]) -> Optional[RemediationContext]:
    """Parse a ``check_run`` webhook payload into a :class:`RemediationContext`.

    Only ``completed`` actions with a failing conclusion on a check associated
    with at least one PR are eligible.  Returns *None* for ineligible payloads.
    """
    action = payload.get('action')
    if action != 'completed':
        return None
    check_run = payload.get('check_run') or {}
    conclusion = check_run.get('conclusion') or ''
    if conclusion not in _FAILED_CONCLUSIONS:
        return None

    repo = payload.get('repository') or {}
    repo_full_name = repo.get('full_name', '')
    installation = payload.get('installation') or {}
    installation_id = installation.get('id')

    if not repo_full_name or not installation_id:
        return None

    head_sha = check_run.get('head_sha') or ''
    check_name = check_run.get('name') or ''
    details_url = check_run.get('details_url') or ''
    app_slug = check_run.get('app', {}).get('slug')
    app_id = check_run.get('app', {}).get('id')

    # Extract PR number / branch from the pull_requests array
    pr_number: int | None = None
    branch = ''
    for pr in check_run.get('pull_requests') or []:
        pr_number = pr.get('number')
        branch = (pr.get('head', {}).get('ref') or
                  check_run.get('head_branch') or '')
        break  # first PR is enough

    return RemediationContext(
        repo_full_name=repo_full_name,
        installation_id=int(installation_id),
        head_sha=head_sha,
        check_name=check_name,
        conclusion=conclusion,
        details_url=details_url,
        event_type='check_run',
        pr_number=pr_number,
        branch=branch,
        app_slug=app_slug,
        app_id=app_id,
    )


def parse_check_suite(payload: dict[str, Any]) -> Optional[RemediationContext]:
    """Parse a ``check_suite`` webhook payload.

    ``check_suite.completed`` events are coarser than individual check runs.
    We create a single remediation context keyed on the suite rather than
    each individual check within it.
    """
    action = payload.get('action')
    if action != 'completed':
        return None
    check_suite = payload.get('check_suite') or {}
    conclusion = check_suite.get('conclusion') or ''
    if conclusion not in _FAILED_CONCLUSIONS:
        return None

    repo = payload.get('repository') or {}
    repo_full_name = repo.get('full_name', '')
    installation = payload.get('installation') or {}
    installation_id = installation.get('id')
    if not repo_full_name or not installation_id:
        return None

    head_sha = check_suite.get('head_sha') or ''
    check_name = f'check-suite:{check_suite.get("id", "unknown")}'
    details_url = check_suite.get('url') or ''
    app_slug = check_suite.get('app', {}).get('slug')
    app_id = check_suite.get('app', {}).get('id')

    pr_number: int | None = None
    branch = ''
    for pr in check_suite.get('pull_requests') or []:
        pr_number = pr.get('number')
        branch = pr.get('head', {}).get('ref') or ''
        break

    return RemediationContext(
        repo_full_name=repo_full_name,
        installation_id=int(installation_id),
        head_sha=head_sha,
        check_name=check_name,
        conclusion=conclusion,
        details_url=details_url,
        event_type='check_suite',
        pr_number=pr_number,
        branch=branch,
        app_slug=app_slug,
        app_id=app_id,
    )


def parse_workflow_run(payload: dict[str, Any]) -> Optional[RemediationContext]:
    """Parse a ``workflow_run`` webhook payload."""
    action = payload.get('action')
    if action != 'completed':
        return None
    workflow_run = payload.get('workflow_run') or {}
    conclusion = workflow_run.get('conclusion') or ''
    if conclusion not in _FAILED_CONCLUSIONS:
        return None

    repo = payload.get('repository') or {}
    repo_full_name = repo.get('full_name', '')
    installation = payload.get('installation') or {}
    installation_id = installation.get('id')
    if not repo_full_name or not installation_id:
        return None

    head_sha = workflow_run.get('head_sha') or ''
    check_name = workflow_run.get('name') or ''
    details_url = workflow_run.get('html_url') or ''
    branch = workflow_run.get('head_branch') or ''

    # workflow_run payloads embed pull_requests since GitHub REST v3
    pr_number: int | None = None
    for pr in workflow_run.get('pull_requests') or []:
        pr_number = pr.get('number')
        if not branch:
            branch = pr.get('head', {}).get('ref') or ''
        break

    return RemediationContext(
        repo_full_name=repo_full_name,
        installation_id=int(installation_id),
        head_sha=head_sha,
        check_name=check_name,
        conclusion=conclusion,
        details_url=details_url,
        event_type='workflow_run',
        pr_number=pr_number,
        branch=branch,
        app_slug=None,
        app_id=None,
    )


# ---------------------------------------------------------------------------
# Normalizer dispatcher
# ---------------------------------------------------------------------------

_EVENT_PARSERS = {
    'check_run': parse_check_run,
    'check_suite': parse_check_suite,
    'workflow_run': parse_workflow_run,
}


def normalize_check_event(event_name: str, payload: dict[str, Any]) -> Optional[RemediationContext]:
    """Normalize any supported check event into a :class:`RemediationContext`."""
    parser = _EVENT_PARSERS.get(event_name)
    if not parser:
        return None
    return parser(payload)


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

def is_duplicate(ctx: RemediationContext) -> bool:
    """Return *True* if a remediation task for this context was already created."""
    return ctx.dedup_key in _seen_dedup_keys


def mark_seen(ctx: RemediationContext) -> None:
    """Record the dedup key so future deliveries are suppressed."""
    _seen_dedup_keys.add(ctx.dedup_key)


def reset_seen_keys() -> None:
    """Clear the in-process dedup set (for testing)."""
    _seen_dedup_keys.clear()


# ---------------------------------------------------------------------------
# Worker prompt
# ---------------------------------------------------------------------------

def remediation_prompt(ctx: RemediationContext) -> str:
    """Build the actionable worker prompt for a failed-check remediation task."""
    pr_line = f'\n- Pull request: #{ctx.pr_number}' if ctx.pr_number else ''
    branch_line = f'\n- Branch: `{ctx.branch}`' if ctx.branch else ''
    return f"""You are remediating a failed GitHub check on an open pull request.

## Failed check details
- Repository: {ctx.repo_full_name}
- Check name: {ctx.check_name}
- Conclusion: {ctx.conclusion}
- Head SHA: `{ctx.head_sha}`
- Details URL: {ctx.details_url}{pr_line}{branch_line}
- Event source: {ctx.event_type}

## Instructions

1. **Fetch the logs.** Use the Details URL above or the GitHub API to retrieve
   the failed check logs and understand the root cause.
2. **Checkout the branch** `{ctx.branch or ctx.head_sha}` in the workspace.
3. **Patch the code** to fix the failure. Prefer minimal, targeted edits.
4. **Validate locally** by running the smallest relevant test or lint command
   that reproduces the failure.
5. **Commit and push** to the existing branch. Do NOT merge the PR.
6. **Comment on the PR** with a short evidence summary:
   - What failed and why.
   - What was changed.
   - Validation output confirming the fix.

## Constraints

- Do NOT merge the pull request.
- Do NOT force-push.
- If you cannot determine the fix, comment on the PR with a blocker summary
  instead of silently failing.
- Use CodeTether's concise, provenance-aware voice in all GitHub comments.

## Provenance

This task was created automatically by the CodeTether failed-check remediation
loop.  Issue #88 / branch `codetether/issue-88`."""

