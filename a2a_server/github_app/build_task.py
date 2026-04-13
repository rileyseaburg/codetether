"""Build-task creation for GitHub App PR fix workflows."""

from .context import MentionContext
from .prompt import fix_prompt
from .routing import resolve_task_target
from .settings import MODEL_REF


async def create_build_task(
    context: MentionContext, pr: dict, wid: str, clone_worker_id: str | None
) -> str:
    """Queue the post-clone edit task on the worker that prepared the repo."""
    from ..monitor_api import AgentTaskCreate, create_agent_task

    metadata = {
        'workspace_id': wid,
        'source': 'github-app',
        'repo': context.repo_full_name,
        'pr_number': context.pr_number,
        'pr_head': pr['head']['ref'],
        'pr_base': pr['base']['ref'],
        'comment_path': context.comment_path,
        'comment_diff_hunk': context.comment_diff_hunk,
        **(await resolve_task_target()),
    }
    if clone_worker_id:
        metadata['target_worker_id'] = clone_worker_id
    task = await create_agent_task(
        wid,
        AgentTaskCreate(
            title=f'Apply PR fix #{context.pr_number}',
            prompt=fix_prompt(context, pr),
            agent_type='build',
            metadata=metadata,
            model_ref=MODEL_REF,
        ),
    )
    return getattr(task, 'id', None) or task.get('id')
