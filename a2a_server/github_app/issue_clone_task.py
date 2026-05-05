"""Clone-task creation for GitHub App issue workflows."""

from .context import MentionContext
from .issue_prompt import issue_fix_prompt
from .routing import resolve_task_target
from .settings import MODEL_REF

DEFAULT_TASK_TIMEOUT = 604800  # 7 days


async def create_issue_clone_task(
    context: MentionContext,
    issue: dict,
    repo: dict,
    wid: str,
    branch: str,
    *,
    github_issue_url: str = '',
    github_installation_id: int = 0,
) -> str:
    """Queue the branch preparation task for an issue fix request.

    Dispatches as fire-and-forget with a 7-day timeout so the persistent
    worker (harvester) can claim it and run it on our compute.

    The github_issue_url is propagated into the clone and follow-up build
    task metadata so the progress reporter can post periodic comments.
    """
    from ..persistent_worker_pool import create_and_dispatch_task

    base_branch = repo['default_branch']

    followup_metadata = {
        'workspace_id': wid,
        'source': 'github-app',
        'workflow_stage': 'code',
        'repo': context.repo_full_name,
        'issue_number': context.issue_number,
        'branch_name': branch,
        'default_branch': base_branch,
        'github_issue_url': github_issue_url,
        'github_installation_id': github_installation_id,
        'worker_personality': 'builder',
        'personality': {
            'name': 'CodeTether',
            'avatar': 'codetether-avatar',
            'tone': 'concise, implementation-focused, provenance-aware',
        },
        'codetether_provenance': {
            'workflow': 'github-issue-code-pr-review-merge',
            'stage': 'code',
            'repo': context.repo_full_name,
            'issue_number': context.issue_number,
            'branch': branch,
            'installation_id': github_installation_id,
        },
    }

    routing = await resolve_task_target()

    metadata = {
        'workspace_id': wid,
        'git_url': repo['clone_url'],
        'git_branch': base_branch,
        'source': 'github-app',
        'repo': context.repo_full_name,
        'issue_number': context.issue_number,
        'github_issue_url': github_issue_url,
        'github_installation_id': github_installation_id,
        **routing,
        'post_clone_task': {
            'title': f'Work issue #{context.issue_number}',
            'prompt': issue_fix_prompt(context, issue, repo, branch),
            'agent_type': 'build',
            'metadata': followup_metadata,
        },
    }
    return await create_and_dispatch_task(
        workspace_id=wid,
        title=f'Prepare issue workspace #{context.issue_number}',
        prompt=f'Clone or refresh {context.repo_full_name} on branch {base_branch} for issue automation.',
        agent_type='clone_repo',
        model_ref=MODEL_REF,
        metadata=metadata,
        task_timeout_seconds=DEFAULT_TASK_TIMEOUT,
        github_issue_url=github_issue_url,
    )
