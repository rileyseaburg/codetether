"""Webhook payload parsing for GitHub App comment handling."""

from typing import Any, Optional

from .context import MentionContext
from .mention import mentions_bot


def extract_context(event_name: str, payload: dict[str, Any]) -> Optional[MentionContext]:
    """Normalize issue-comment, review-comment, and review webhook payloads."""
    if event_name == 'pull_request_review':
        comment = payload.get('review') or {}
    else:
        comment = payload.get('comment') or {}
    body = comment.get('body', '')
    installation_id = payload.get('installation', {}).get('id')
    repo_full_name = payload.get('repository', {}).get('full_name', '')
    comment_id = comment.get('id')
    if not mentions_bot(body) or not installation_id or not repo_full_name or not comment_id:
        return None
    if event_name == 'issue_comment':
        issue = payload.get('issue', {})
        issue_number = issue.get('number')
        pr_number = issue_number if issue.get('pull_request') else None
    elif event_name in {'pull_request_review_comment', 'pull_request_review'}:
        issue_number = payload.get('pull_request', {}).get('number')
        pr_number = issue_number
    else:
        return None
    if not issue_number:
        return None
    return MentionContext(
        repo_full_name=repo_full_name,
        installation_id=int(installation_id),
        issue_number=int(issue_number),
        pr_number=int(pr_number) if pr_number else None,
        comment_id=int(comment_id),
        comment_body=body,
        comment_path=comment.get('path', '') or '',
        comment_diff_hunk=comment.get('diff_hunk', '') or '',
    )
