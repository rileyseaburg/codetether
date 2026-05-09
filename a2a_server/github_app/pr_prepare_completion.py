"""Follow-up creation for GitHub App PR prepare tasks."""

from .settings import MODEL_REF
from .task_context import github_app_task_context
from .watch import post_issue_comment

DEFAULT_TASK_TIMEOUT = 604800  # 7 days


async def handle_pr_prepare_completion(task: dict, worker_id: str | None = None) -> None:
    """Create the PR branch edit task or post a prepare failure."""
    from ..persistent_worker_pool import create_and_dispatch_task

    metadata = task.get('metadata') or {}
    context = await github_app_task_context(task)
    if context is None:
        return
    repo, pr_number, _, token = context
    if str(task.get('status')) != 'completed':
        body = str(
            task.get('error')
            or task.get('result')
            or f"Task `{task.get('id')}` ended with status `{task.get('status')}`."
        ).strip()
        await post_issue_comment(
            repo,
            pr_number,
            token,
            f"## 🛠️ CodeTether Fix\n\nI couldn't prepare the PR workspace.\n\n{body}",
        )
        return

    followup = metadata.get('post_clone_task') or {}
    workspace_id = str(metadata.get('workspace_id') or '').strip()
    prompt = str(followup.get('prompt') or '').strip()
    if not workspace_id or not prompt:
        await post_issue_comment(
            repo,
            pr_number,
            token,
            "## 🛠️ CodeTether Fix\n\nI prepared the PR workspace, but the follow-up task metadata was incomplete.",
        )
        return

    followup_metadata = dict(followup.get('metadata') or {})

    # Propagate github_issue_url and github_installation_id for progress reporting
    for key in ('github_issue_url', 'github_installation_id'):
        if key in metadata and key not in followup_metadata:
            followup_metadata[key] = metadata[key]

    target_worker_id = str(worker_id or task.get('worker_id') or '').strip()
    if target_worker_id:
        followup_metadata['target_worker_id'] = target_worker_id

    github_issue_url = followup_metadata.get('github_issue_url') or metadata.get('github_issue_url')
    await create_and_dispatch_task(
        workspace_id=workspace_id,
        title=str(followup.get('title') or f'Apply PR fix #{pr_number}'),
        prompt=prompt,
        agent_type=str(followup.get('agent_type') or 'build'),
        model_ref=MODEL_REF,
        metadata=followup_metadata,
        task_timeout_seconds=DEFAULT_TASK_TIMEOUT,
        github_issue_url=github_issue_url,
    )
