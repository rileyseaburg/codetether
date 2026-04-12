"""Clone-task creation for GitHub App issue workflows."""

from .context import MentionContext
from .issue_prompt import issue_fix_prompt
from .routing import resolve_task_target
from .settings import MODEL_REF


async def create_issue_clone_task(
    context: MentionContext, issue: dict, repo: dict, wid: str, branch: str
) -> str:
    """Queue the branch preparation task for an issue fix request."""
    from ..monitor_api import AgentTaskCreate, create_agent_task

    base_branch = repo['default_branch']
    metadata = {
        'workspace_id': wid,
        'git_url': repo['clone_url'],
        'git_branch': base_branch,
        'source': 'github-app',
        'repo': context.repo_full_name,
        'issue_number': context.issue_number,
        **(await resolve_task_target()),
        'post_clone_task': {
            'title': f'Work issue #{context.issue_number}',
            'prompt': issue_fix_prompt(context, issue, repo, branch),
            'agent_type': 'build',
            'metadata': {'workspace_id': wid, 'source': 'github-app', 'repo': context.repo_full_name, 'issue_number': context.issue_number, 'branch_name': branch, 'default_branch': repo['default_branch']},
        },
    }
    task = await create_agent_task(
        wid,
        AgentTaskCreate(
            title=f'Prepare issue workspace #{context.issue_number}',
            prompt=f'Clone or refresh {context.repo_full_name} on branch {base_branch} for issue automation.',
            agent_type='clone_repo',
            metadata=metadata,
            model_ref=MODEL_REF,
        ),
    )
    return getattr(task, 'id', None) or task.get('id')
