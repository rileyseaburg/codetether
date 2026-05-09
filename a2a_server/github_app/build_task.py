"""Build-task creation for GitHub App PR fix workflows."""

from .context import MentionContext
from .prompt import fix_prompt
from .routing import resolve_task_target
from .settings import MODEL_REF

DEFAULT_TASK_TIMEOUT = 604800  # 7 days


async def create_build_task(
    context: MentionContext, pr: dict, wid: str, clone_worker_id: str | None
) -> str:
    """Queue the post-clone edit task on the worker that prepared the repo.

    Dispatches as fire-and-forget with a 7-day timeout.
    """
    from ..persistent_worker_pool import create_and_dispatch_task

    routing = await resolve_task_target()
    metadata = {
        'workspace_id': wid,
        'source': 'github-app',
        'repo': context.repo_full_name,
        'pr_number': context.pr_number,
        'pr_head': pr['head']['ref'],
        'pr_base': pr['base']['ref'],
        'comment_path': context.comment_path,
        'comment_diff_hunk': context.comment_diff_hunk,
        'github_issue_url': f'https://github.com/{context.repo_full_name}/pull/{context.pr_number}',
        'github_installation_id': context.installation_id,
        **routing,
    }
    if clone_worker_id:
        metadata['target_worker_id'] = clone_worker_id
    return await create_and_dispatch_task(
        workspace_id=wid,
        title=f'Apply PR fix #{context.pr_number}',
        prompt=fix_prompt(context, pr),
        agent_type='build',
        model_ref=MODEL_REF,
        metadata=metadata,
        task_timeout_seconds=DEFAULT_TASK_TIMEOUT,
        github_issue_url=f'https://github.com/{context.repo_full_name}/pull/{context.pr_number}',
    )
