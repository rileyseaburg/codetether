"""GitHub issue comment utilities for the GitHub App webhook flow.

The synchronous monitor_pr_fix() / wait_for_task() polling path has been
replaced by the event-driven task lifecycle:

  1. Webhook → handler.py creates a clone task and returns immediately.
  2. Clone task completes → pr_prepare_completion / issue_prepare_completion
     creates the follow-up build task.
  3. Build task completes → pr_final_comment / issue_final_comment posts the
     result on the GitHub issue/PR.
  4. For long-running tasks, github_progress_service posts periodic progress
     comments on the issue (every 5 minutes) using the github_issue_url stored
     in task metadata.
  5. If a worker dies, task_reaper detects the missed heartbeat and requeues
     the task (up to max_attempts). On permanent failure, it posts a comment.

All orchestration is event-driven via task_status_hook.py, which is called from
worker_sse.py / hosted_worker.py / monitor_api.py when tasks go terminal.
"""

import logging
from typing import Any

from .auth import github_json

logger = logging.getLogger(__name__)


async def post_issue_comment(
    repo_full_name: str, issue_number: int, token: str, body: str
) -> None:
    """Post a status update back onto the PR issue timeline."""
    await github_json(
        'POST',
        f'/repos/{repo_full_name}/issues/{issue_number}/comments',
        token,
        {'body': body[:65000]},
    )
