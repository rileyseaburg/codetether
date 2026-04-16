"""Workspace and clone-task helpers for GitHub App comment execution."""

import hashlib
from typing import Any

from .context import MentionContext
from .prompt import fix_prompt; from .routing import resolve_task_target
from .settings import MODEL_REF, get_secret


def workspace_id(git_url: str, git_branch: str) -> str:
    """Derive the deterministic branch-scoped workspace ID."""
    return hashlib.sha256(f'{git_url}::{git_branch or "main"}'.encode()).hexdigest()[:16]


def checkout_branch(context: MentionContext, pr: dict[str, Any]) -> str:
    """Return the remote branch that should be cloned into the workspace."""
    return pr['head']['ref'] if context.pr_number else pr['base']['ref']


async def ensure_workspace(context: MentionContext, pr: dict[str, Any]) -> str:
    """Persist a GitHub App workspace so the existing agent APIs can rehydrate it."""
    from .. import database as db
    from ..monitor_api import _redis_upsert_workspace_meta

    git_url = pr['head']['repo']['clone_url']
    branch_name = pr['head']['ref']
    git_branch = checkout_branch(context, pr)
    app_id = await get_secret('app_id', 'GITHUB_APP_ID', 'app_id', 'github_app_id')
    wid = workspace_id(git_url, git_branch)
    workspace = {'id': wid, 'name': context.repo_full_name, 'path': f'/var/lib/codetether/repos/{wid}', 'description': f'GitHub App workspace for {context.repo_full_name}', 'git_url': git_url, 'git_branch': git_branch, 'status': 'active', 'agent_config': {'source': 'github-app', 'repo': {'full_name': context.repo_full_name}, 'github': {'repo_full_name': context.repo_full_name, 'pull_request_number': context.pr_number, 'branch_name': branch_name}, 'git_auth': {'github_app': {'app_id': app_id, 'installation_id': str(context.installation_id)}}}}
    await db.db_upsert_workspace(workspace)
    await _redis_upsert_workspace_meta(workspace)
    return wid


async def create_clone_task(context: MentionContext, pr: dict[str, Any], wid: str) -> str:
    """Queue a targeted clone/refresh task for the PR branch."""
    from ..monitor_api import AgentTaskCreate, create_agent_task

    metadata = {
        'workspace_id': wid,
        'git_url': pr['head']['repo']['clone_url'],
        'git_branch': pr['head']['ref'],
        'source': 'github-app',
        'repo': context.repo_full_name,
        'pr_number': context.pr_number,
        **(await resolve_task_target()),
        'post_clone_task': {
            'title': f'Apply PR fix #{context.pr_number}',
            'prompt': fix_prompt(context, pr),
            'agent_type': 'build',
            'metadata': {
                'workspace_id': wid,
                'source': 'github-app',
                'repo': context.repo_full_name,
                'pr_number': context.pr_number,
                'pr_head': pr['head']['ref'],
                'pr_base': pr['base']['ref'],
                'comment_path': context.comment_path,
                'comment_diff_hunk': context.comment_diff_hunk,
            },
        },
    }
    task = await create_agent_task(wid, AgentTaskCreate(title=f'Prepare PR workspace #{context.pr_number}', prompt=f'Clone or refresh {context.repo_full_name} on branch {pr["head"]["ref"]} for PR fix execution.', agent_type='clone_repo', metadata=metadata, model_ref=MODEL_REF))
    # create_agent_task returns {'success': True, 'task': {...}}
    task_dict = task if isinstance(task, dict) else {}
    task_data = task_dict.get('task', task_dict)
    return task_data.get('id') or getattr(task, 'id', None)
