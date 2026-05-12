"""Webhook payload parsing for GitHub App mention handling."""

from typing import Any, Optional

from .context import MentionContext
from .mention import mentions_bot


def is_supported_event_action(event_name: str, payload: dict[str, Any]) -> bool:
    """Return true when a webhook event can carry a new actionable mention."""
    action = payload.get('action')
    if event_name in {'issue_comment', 'pull_request_review_comment'}:
        return action == 'created'
    if event_name == 'pull_request_review':
        return action == 'submitted'
    if event_name in {'issues', 'pull_request'}:
        if action == 'opened':
            return True
        if action == 'edited':
            old_body = (payload.get('changes', {}).get('body', {}) or {}).get('from', '')
            new_body = _body_for_event(event_name, payload)
            return mentions_bot(new_body) and not mentions_bot(old_body)
    return False


def _body_for_event(event_name: str, payload: dict[str, Any]) -> str:
    if event_name in {'issue_comment', 'pull_request_review_comment'}:
        return payload.get('comment', {}).get('body', '') or ''
    if event_name == 'pull_request_review':
        return payload.get('review', {}).get('body', '') or ''
    if event_name == 'issues':
        return payload.get('issue', {}).get('body', '') or ''
    if event_name == 'pull_request':
        return payload.get('pull_request', {}).get('body', '') or ''
    return ''


def extract_context(event_name: str, payload: dict[str, Any]) -> Optional[MentionContext]:
    """Normalize GitHub webhook payloads that can mention the app."""
    body = _body_for_event(event_name, payload)
    installation_id = payload.get('installation', {}).get('id')
    repo_full_name = payload.get('repository', {}).get('full_name', '')
    comment_id = payload.get('comment', {}).get('id')
    issue_number = None
    pr_number = None
    comment_path = ''
    comment_diff_hunk = ''

    if not mentions_bot(body) or not installation_id or not repo_full_name:
        return None

    if event_name == 'issue_comment':
        issue = payload.get('issue', {})
        issue_number = issue.get('number')
        pr_number = issue_number if issue.get('pull_request') else None
    elif event_name == 'pull_request_review_comment':
        issue_number = payload.get('pull_request', {}).get('number')
        pr_number = issue_number
        comment_path = payload.get('comment', {}).get('path', '') or ''
        comment_diff_hunk = payload.get('comment', {}).get('diff_hunk', '') or ''
    elif event_name == 'pull_request_review':
        issue_number = payload.get('pull_request', {}).get('number')
        pr_number = issue_number
        review = payload.get('review') or {}
        comment_id = review.get('id') or issue_number
    elif event_name == 'issues':
        issue = payload.get('issue', {})
        issue_number = issue.get('number')
        pr_number = issue_number if issue.get('pull_request') else None
        comment_id = issue.get('id') or issue_number
    elif event_name == 'pull_request':
        pr = payload.get('pull_request', {})
        issue_number = pr.get('number')
        pr_number = issue_number
        comment_id = pr.get('id') or issue_number
    else:
        return None

    if not issue_number or not comment_id:
        return None
    return MentionContext(
        repo_full_name=repo_full_name,
        installation_id=int(installation_id),
        issue_number=int(issue_number),
        pr_number=int(pr_number) if pr_number else None,
        comment_id=int(comment_id),
        comment_body=body,
        comment_path=comment_path,
        comment_diff_hunk=comment_diff_hunk,
    )
