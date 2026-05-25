"""Build-task creation for GitHub App issue workflows."""

from .context import MentionContext
from .issue_prompt import issue_fix_prompt
from .routing import resolve_task_target
from .settings import MODEL_REF

DEFAULT_TASK_TIMEOUT = 604800  # 7 days


async def create_issue_build_task(
    context: MentionContext,
    issue: dict,
    repo: dict,
    wid: str,
    branch: str,
    clone_worker_id: str | None,
) -> str:
    """Queue the post-clone build task for the durable GitHub App worker pool.

    Dispatches as fire-and-forget with a 7-day timeout.
    """
    from ..persistent_worker_pool import create_and_dispatch_task

    routing = await resolve_task_target()
    metadata = {
        'workspace_id': wid,
        'source': 'github-app',
        'repo': context.repo_full_name,
        'issue_number': context.issue_number,
        'branch_name': branch,
        'default_branch': repo['default_branch'],
        'github_issue_url': f'https://github.com/{context.repo_full_name}/issues/{context.issue_number}',
        'github_installation_id': context.installation_id,
        **routing,
    }
    return await create_and_dispatch_task(
        workspace_id=wid,
        title=f'Work issue #{context.issue_number}',
        prompt=issue_fix_prompt(context, issue, repo, branch),
        agent_type='build',
        model_ref=MODEL_REF,
        metadata=metadata,
        task_timeout_seconds=DEFAULT_TASK_TIMEOUT,
        github_issue_url=f'https://github.com/{context.repo_full_name}/issues/{context.issue_number}',
    )
