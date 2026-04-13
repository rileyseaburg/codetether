"""Build-task creation for GitHub App issue workflows."""

from .context import MentionContext
from .issue_prompt import issue_fix_prompt
from .routing import resolve_task_target
from .settings import MODEL_REF


async def create_issue_build_task(
    context: MentionContext,
    issue: dict,
    repo: dict,
    wid: str,
    branch: str,
    clone_worker_id: str | None,
) -> str:
    """Queue the post-clone build task for an issue fix request."""
    from ..monitor_api import AgentTaskCreate, create_agent_task

    metadata = {
        'workspace_id': wid,
        'source': 'github-app',
        'repo': context.repo_full_name,
        'issue_number': context.issue_number,
        'branch_name': branch,
        'default_branch': repo['default_branch'],
        **(await resolve_task_target()),
    }
    if clone_worker_id:
        metadata['target_worker_id'] = clone_worker_id
    task = await create_agent_task(
        wid,
        AgentTaskCreate(
            title=f'Work issue #{context.issue_number}',
            prompt=issue_fix_prompt(context, issue, repo, branch),
            agent_type='build',
            metadata=metadata,
            model_ref=MODEL_REF,
        ),
    )
    return getattr(task, 'id', None) or task.get('id')
