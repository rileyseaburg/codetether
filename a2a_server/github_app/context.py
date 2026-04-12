"""Shared GitHub App webhook context types."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class MentionContext:
    """Normalized GitHub comment context for webhook handling."""

    repo_full_name: str
    installation_id: int
    issue_number: int
    pr_number: Optional[int]
    comment_id: int
    comment_body: str
    comment_path: str = ''
    comment_diff_hunk: str = ''
