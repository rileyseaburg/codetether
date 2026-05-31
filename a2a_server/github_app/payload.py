"""Webhook payload parsing for GitHub App mention handling."""

from typing import Any, Optional

from .context import MentionContext
from .mention import mentions_bot
from .settings import APP_SLUG


def _actor_for_event(
    event_name: str, payload: dict[str, Any]
) -> dict[str, Any]:
    """Return the GitHub actor that authored the user-visible webhook text."""
    if event_name in {'issue_comment', 'pull_request_review_comment'}:
        return payload.get('comment', {}).get('user', {}) or {}
    if event_name == 'pull_request_review':
        return payload.get('review', {}).get('user', {}) or {}
    if event_name == 'issues':
        return payload.get('issue', {}).get('user', {}) or {}
    if event_name == 'pull_request':
        return payload.get('pull_request', {}).get('user', {}) or {}
    return payload.get('sender', {}) or {}


def is_self_authored_event(event_name: str, payload: dict[str, Any]) -> bool:
    """Return true when this GitHub App authored the webhook text.

    GitHub emits normal comment webhooks for comments posted by the App's
    installation token. Several CodeTether status/guidance comments include
    examples such as ``@codetether handle this issue``; without this guard the
    App can interpret its own comment as a fresh fix request and keep replying
    to itself.
    """
    app_slug = APP_SLUG.lower()
    expected_bot_login = f'{app_slug}[bot]'
    actors = [
        _actor_for_event(event_name, payload),
        payload.get('sender', {}) or {},
    ]
    for actor in actors:
        login = str(actor.get('login', '') or '').lower()
        actor_type = str(actor.get('type', '') or '').lower()
        if login == expected_bot_login:
            return True
        if actor_type == 'bot' and login.startswith(app_slug):
            return True
    return False


def is_supported_event_action(event_name: str, payload: dict[str, Any]) -> bool:
    """Return true when a webhook event can carry a new actionable mention."""
    action = payload.get('action')
    if is_self_authored_event(event_name, payload):
        return False
    if event_name in {'issue_comment', 'pull_request_review_comment'}:
        if action == 'created':
            return True
        if action == 'edited':
            old_body = (payload.get('changes', {}).get('body', {}) or {}).get(
                'from', ''
            )
            new_body = _body_for_event(event_name, payload)
            return mentions_bot(new_body) and not mentions_bot(old_body)
        return False
    if event_name == 'pull_request_review':
        return action == 'submitted'
    if event_name in {'issues', 'pull_request'}:
        if action == 'opened':
            return True
        if action == 'edited':
            old_body = (payload.get('changes', {}).get('body', {}) or {}).get(
                'from', ''
            )
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


def is_changes_requested_review(
    event_name: str, payload: dict[str, Any]
) -> bool:
    """Return true for PR review submissions that request changes."""
    if event_name != 'pull_request_review':
        return False
    review = payload.get('review') or {}
    return str(review.get('state') or '').lower() == 'changes_requested'


def _changes_requested_review_body(payload: dict[str, Any]) -> str:
    review = payload.get('review') or {}
    reviewer = (review.get('user') or {}).get('login') or 'unknown'
    review_body = str(review.get('body') or '').strip()
    body = f'@codetether please address the requested PR changes. Changes requested by reviewer {reviewer}.'
    if review_body:
        body = f'{body}\n\n{review_body}'
    return body


def extract_context(
    event_name: str, payload: dict[str, Any]
) -> Optional[MentionContext]:
    """Normalize GitHub webhook payloads that can mention the app."""
    body = _body_for_event(event_name, payload)
    installation_id = payload.get('installation', {}).get('id')
    repo_full_name = payload.get('repository', {}).get('full_name', '')
    comment_id = payload.get('comment', {}).get('id')
    issue_number = None
    pr_number = None
    comment_path = ''
    comment_diff_hunk = ''

    is_review_change_request = is_changes_requested_review(event_name, payload)
    if (
        (not is_review_change_request and not mentions_bot(body))
        or not installation_id
        or not repo_full_name
    ):
        return None

    if event_name == 'issue_comment':
        issue = payload.get('issue', {})
        issue_number = issue.get('number')
        pr_number = issue_number if issue.get('pull_request') else None
    elif event_name == 'pull_request_review_comment':
        issue_number = payload.get('pull_request', {}).get('number')
        pr_number = issue_number
        comment_path = payload.get('comment', {}).get('path', '') or ''
        comment_diff_hunk = (
            payload.get('comment', {}).get('diff_hunk', '') or ''
        )
    elif event_name == 'pull_request_review':
        issue_number = payload.get('pull_request', {}).get('number')
        pr_number = issue_number
        review = payload.get('review') or {}
        comment_id = review.get('id') or issue_number
        if is_review_change_request and not mentions_bot(body):
            body = _changes_requested_review_body(payload)
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
