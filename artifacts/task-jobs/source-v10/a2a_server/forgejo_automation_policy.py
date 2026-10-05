"""Explicit consent and containment controls for repository-changing automation."""

import os


def status_remediation_enabled() -> bool:
    """Require opt-in for unsolicited edits triggered by failed CI statuses."""
    return os.getenv('FORGEJO_STATUS_REMEDIATION_ENABLED', '').lower() in {
        '1',
        'true',
        'yes',
    }


def pr_is_paused(repo: str, number: int) -> bool:
    """Honor exact repository/PR holds without blocking unrelated repositories."""
    paused = {
        item.strip().casefold()
        for item in os.getenv('FORGEJO_AUTOMATION_PAUSED_PRS', '').split(',')
        if item.strip()
    }
    return f'{repo}#{number}'.casefold() in paused


def self_review_status(context: str) -> bool:
    """Do not recursively edit code to repair this bot's own review workflow."""
    name = context.strip().casefold()
    return name.startswith(
        ('codetether/', 'codetether pr review', 'codetether review')
    )
