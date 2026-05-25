"""Follow-up creation for GitHub App issue prepare tasks."""

from .pr_prepare_completion import (
    _acquire_followup_lock,
    _active_followup_task_id,
    _claim_pr_followup_creation,
    _record_pr_followup_task,
    _release_followup_lock,
    _release_pr_followup_claim,
)
from .settings import MODEL_REF
from .task_context import issue_task_context
from .watch import post_issue_comment

DEFAULT_TASK_TIMEOUT = 604800  # 7 days


async def handle_issue_prepare_completion(task: dict, worker_id: str | None = None) -> None:
    """Create the issue build task or post a prepare failure."""
    from ..persistent_worker_pool import create_and_dispatch_task

    metadata = task.get('metadata') or {}
    context = await issue_task_context(task)
    if context is None:
        return
    repo, issue_number, _, token = context
    if str(task.get('status')) != 'completed':
        body = str(task.get('error') or task.get('result') or f"Task `{task.get('id')}` ended with status `{task.get('status')}`.").strip()
        await post_issue_comment(repo, issue_number, token, f"## 🛠️ CodeTether Fix\n\nI couldn't prepare the issue workspace.\n\n{body}")
        return
    followup = metadata.get('post_clone_task') or {}
    workspace_id = str(metadata.get('workspace_id') or '').strip()
    prompt = str(followup.get('prompt') or '').strip()
    if not workspace_id or not prompt:
        await post_issue_comment(repo, issue_number, token, "## 🛠️ CodeTether Fix\n\nI prepared the workspace, but the follow-up task metadata was incomplete.")
        return
    followup_metadata = dict(followup.get('metadata') or {})

    # Propagate GitHub metadata for progress reporting and Checks API updates.
    for key in ('github_issue_url', 'github_installation_id', 'github_check_head_sha', 'github_check_run_id'):
        if key in metadata and key not in followup_metadata:
            followup_metadata[key] = metadata[key]

    source_task_id = str(task.get('id') or '').strip() or None
    if not await _claim_pr_followup_creation(source_task_id):
        return

    github_issue_url = followup_metadata.get('github_issue_url') or metadata.get('github_issue_url')
    lock = await _acquire_followup_lock(repo, issue_number, 'issue')
    try:
        existing_task_id = await _active_followup_task_id(
            repo,
            issue_number,
            'issue',
        )
        if existing_task_id:
            await _record_pr_followup_task(source_task_id, existing_task_id)
            return

        followup_task_id = await create_and_dispatch_task(
            workspace_id=workspace_id,
            title=str(followup.get('title') or f'Work issue #{issue_number}'),
            prompt=prompt,
            agent_type=str(followup.get('agent_type') or 'build'),
            model_ref=MODEL_REF,
            metadata=followup_metadata,
            task_timeout_seconds=DEFAULT_TASK_TIMEOUT,
            github_issue_url=github_issue_url,
        )
    except Exception as exc:
        await _release_pr_followup_claim(source_task_id, exc)
        raise
    finally:
        await _release_followup_lock(lock)
    await _record_pr_followup_task(source_task_id, followup_task_id)
