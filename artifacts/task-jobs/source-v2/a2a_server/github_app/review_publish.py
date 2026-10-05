"""Publish CodeTether reviewer-task results as GitHub pull request reviews."""

from __future__ import annotations

import logging
from typing import Any

from a2a_server.github_app.auth import github_json
from a2a_server.github_app.issue_review_task import reviewer_verdict


logger = logging.getLogger(__name__)

_REVIEW_BODY_LIMIT = 60_000


def review_marker(task_id: str) -> str:
    """Return the stable marker used to suppress duplicate review publication."""
    return f'<!-- codetether-review-task:{task_id} -->'


def review_event(review_task: dict[str, Any]) -> str:
    """Map a CodeTether reviewer verdict to a GitHub review event."""
    verdict = reviewer_verdict(review_task)
    if verdict == 'APPROVED':
        return 'APPROVE'
    if verdict in {'CHANGES_REQUESTED', 'BLOCKED'}:
        return 'REQUEST_CHANGES'
    return 'COMMENT'


def review_body(review_task: dict[str, Any]) -> str:
    """Build the first-class GitHub review body with idempotency evidence."""
    task_id = str(review_task.get('id') or '').strip()
    verdict = reviewer_verdict(review_task) or 'COMMENT'
    result = str(
        review_task.get('result')
        or review_task.get('error')
        or 'CodeTether reviewer task completed without a textual summary.'
    ).strip()
    marker = review_marker(task_id)
    prefix = f'## CodeTether Review\n\n**Verdict:** `{verdict}`\n\n'
    available = max(0, _REVIEW_BODY_LIMIT - len(prefix) - len(marker) - 2)
    return f'{prefix}{result[:available]}\n\n{marker}'


async def publish_github_review(
    review_task: dict[str, Any],
    token: str,
) -> dict[str, Any]:
    """Publish one idempotent GitHub PR review for a reviewer task.

    GitHub does not allow an App to approve or request changes on a PR authored
    by that same App. When the semantic event is rejected, publish the same
    verdict and evidence as a first-class ``COMMENT`` review instead. Existing
    reviews carrying this task's hidden marker are returned without reposting.
    """
    metadata = review_task.get('metadata') or {}
    task_id = str(review_task.get('id') or '').strip()
    repo = str(metadata.get('repo') or '').strip()
    pr_number = int(metadata.get('pr_number') or 0)
    head_sha = str(
        metadata.get('pr_head_sha')
        or metadata.get('github_check_head_sha')
        or ''
    ).strip()
    if not (task_id and repo and pr_number and token):
        raise ValueError('review task is missing GitHub publication context')

    marker = review_marker(task_id)
    reviews = await github_json(
        'GET',
        f'/repos/{repo}/pulls/{pr_number}/reviews?per_page=100',
        token,
    )
    for review in reviews or []:
        if marker in str((review or {}).get('body') or ''):
            return {
                'published': True,
                'duplicate': True,
                'event': str((review or {}).get('state') or 'COMMENT'),
                'review_id': (review or {}).get('id'),
            }

    event = review_event(review_task)
    payload: dict[str, Any] = {
        'body': review_body(review_task),
        'event': event,
    }
    if head_sha:
        payload['commit_id'] = head_sha

    path = f'/repos/{repo}/pulls/{pr_number}/reviews'
    try:
        published = await github_json('POST', path, token, payload)
        return {
            'published': True,
            'duplicate': False,
            'event': event,
            'review_id': (published or {}).get('id'),
        }
    except Exception as exc:
        if event == 'COMMENT':
            raise
        logger.info(
            'GitHub rejected %s review for task %s; retrying as COMMENT: %s',
            event,
            task_id,
            exc,
        )
        comment_payload = {**payload, 'event': 'COMMENT'}
        published = await github_json('POST', path, token, comment_payload)
        return {
            'published': True,
            'duplicate': False,
            'event': 'COMMENT',
            'requested_event': event,
            'review_id': (published or {}).get('id'),
        }
