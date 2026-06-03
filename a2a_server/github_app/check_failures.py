"""Failed GitHub check webhook handling for PR remediation."""

from __future__ import annotations

from typing import Any

from .context import MentionContext
from .settings import APP_SLUG

FAILED_CHECK_CONCLUSIONS = {
    'action_required',
    'cancelled',
    'failure',
    'startup_failure',
    'timed_out',
}
CHECK_FAILURE_EVENTS = {'check_run', 'check_suite', 'workflow_run'}


def check_payload(event_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    if event_name == 'check_run':
        return payload.get('check_run') or {}
    if event_name == 'check_suite':
        return payload.get('check_suite') or {}
    if event_name == 'workflow_run':
        return payload.get('workflow_run') or {}
    return {}


def first_pull_request(event_name: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    check = check_payload(event_name, payload)
    pull_requests = check.get('pull_requests') or payload.get('pull_requests') or []
    return pull_requests[0] if pull_requests else None


def should_remediate_failed_check(event_name: str, payload: dict[str, Any]) -> bool:
    """Return true when a completed failed check should start a CodeTether fix session."""
    if event_name not in CHECK_FAILURE_EVENTS:
        return False
    if payload.get('action') not in {'completed', 'requested_action'}:
        return False
    check = check_payload(event_name, payload)
    if str(check.get('conclusion') or '').lower() not in FAILED_CHECK_CONCLUSIONS:
        return False
    app = check.get('app') or {}
    check_name = str(check.get('name') or check.get('display_title') or '')
    app_slug = str(app.get('slug') or '').lower()
    app_name = str(app.get('name') or '').lower()
    slug = APP_SLUG.lower()
    if check_name.lower().startswith(f'{slug} /') or app_slug == slug or app_name == slug:
        return False
    return first_pull_request(event_name, payload) is not None


def check_output_excerpt(check: dict[str, Any], limit: int = 4000) -> str:
    """Return a compact excerpt from GitHub check output fields, when present."""
    output = check.get('output') or {}
    parts = [
        str(output.get('title') or '').strip(),
        str(output.get('summary') or '').strip(),
        str(output.get('text') or '').strip(),
    ]
    excerpt = '\n\n'.join(part for part in parts if part)
    if len(excerpt) > limit:
        return f'{excerpt[:limit].rstrip()}\n… [truncated]'
    return excerpt


def context_from_failed_check(event_name: str, payload: dict[str, Any]) -> MentionContext:
    """Convert a failed check event into the same context used by PR fix requests."""
    repo_full_name = payload.get('repository', {}).get('full_name', '')
    installation_id = int(payload.get('installation', {}).get('id') or 0)
    pr = first_pull_request(event_name, payload)
    if not pr:
        raise ValueError('failed check payload did not include a pull request')
    pr_number = int(pr['number'])
    check = check_payload(event_name, payload)
    check_name = str(check.get('name') or check.get('display_title') or event_name)
    details_url = str(check.get('details_url') or check.get('html_url') or check.get('url') or '')
    conclusion = str(check.get('conclusion') or '')
    head_sha = str(check.get('head_sha') or check.get('head_branch') or '')
    output_excerpt = check_output_excerpt(check)
    body = (
        f'@{APP_SLUG} fix the failing PR check.\n\n'
        f'Check: {check_name}\n'
        f'Conclusion: {conclusion}\n'
        f'Details URL: {details_url or "(none)"}\n'
        f'Head SHA: {head_sha or "(from PR)"}\n\n'
    )
    if output_excerpt:
        body += f'Check output excerpt:\n```\n{output_excerpt}\n```\n\n'
    body += (
        'Investigate the failing check logs, make the smallest appropriate fix on the PR branch, '
        'commit and push to the same branch, and report validation evidence. Do not merge the PR.'
    )
    return MentionContext(
        repo_full_name=repo_full_name,
        installation_id=installation_id,
        issue_number=pr_number,
        pr_number=pr_number,
        comment_id=int(check.get('id') or 0),
        comment_body=body,
    )
