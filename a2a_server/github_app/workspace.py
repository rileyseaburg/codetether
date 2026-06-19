"""Workspace and clone-task helpers for GitHub App comment execution."""

import hashlib

from typing import Any

from .context import MentionContext
from .prompt import fix_prompt
from .routing import resolve_task_target
from .settings import MODEL_REF, get_secret


DEFAULT_TASK_TIMEOUT = 604800  # 7 days


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
    workspace = {'id': wid, 'name': context.repo_full_name, 'path': f'/var/lib/codetether/repos/{wid}', 'description': f'GitHub App workspace for {context.repo_full_name}', 'git_url': git_url, 'git_branch': git_branch, 'status': 'active', 'agent_config': {'source': 'github-app', 'repo': {'full_name': context.repo_full_name}, 'github': {'repo_full_name': context.repo_full_name, 'pull_request_number': context.pr_number, 'branch_name': branch_name}, 'git_auth': {'github_app': {'app_id': app_id, 'installation_id': str(context.installation_id)}}}, 'git_auth': {'github_app': {'app_id': app_id, 'installation_id': str(context.installation_id)}}}
    await db.db_upsert_workspace(workspace)
    await _redis_upsert_workspace_meta(workspace)
    return wid


async def create_clone_task(
    context: MentionContext,
    pr: dict[str, Any],
    wid: str,
    *,
    github_issue_url: str = '',
    github_installation_id: int = 0,
) -> tuple[str, bool]:
    """Queue a targeted clone/refresh task for the PR branch.

    Dispatches as fire-and-forget with a 7-day timeout so the persistent
    worker (harvester) can claim it and run it on our compute.

    The github_issue_url is stored in the clone task's post_clone_task metadata
    so it propagates to the follow-up build task, enabling the progress reporter
    to post periodic comments on the GitHub issue/PR.

    Returns ``(task_id, created)``. ``created`` is False when an active task for
    the same PR/commit/stage was reused (e.g. a redelivered or duplicate
    webhook), so the caller can skip posting another acceptance comment.
    """
    from ..persistent_worker_pool import create_and_dispatch_task

    followup_metadata = {
        'workspace_id': wid,
        'source': 'github-app',
        'workflow_stage': 'code',
        'repo': context.repo_full_name,
        'pr_number': context.pr_number,
        'pr_head': pr['head']['ref'],
        'pr_base': pr['base']['ref'],
        'pr_head_sha': (pr.get('head') or {}).get('sha'),
        'github_check_head_sha': (pr.get('head') or {}).get('sha'),
        'comment_path': context.comment_path,
        'comment_diff_hunk': context.comment_diff_hunk,
        'github_issue_url': github_issue_url,
        'github_installation_id': github_installation_id,
    }

    routing = await resolve_task_target()
    followup_metadata.update(routing)

    metadata = {
        'workspace_id': wid,
        'git_url': pr['head']['repo']['clone_url'],
        'git_branch': pr['head']['ref'],
        'source': 'github-app',
        'repo': context.repo_full_name,
        'pr_number': context.pr_number,
        'pr_head_sha': (pr.get('head') or {}).get('sha'),
        'github_check_head_sha': (pr.get('head') or {}).get('sha'),
        'github_issue_url': github_issue_url,
        'github_installation_id': github_installation_id,
        **routing,
        'post_clone_task': {
            'title': f'Apply PR fix #{context.pr_number}',
            'prompt': fix_prompt(context, pr),
            'agent_type': 'build',
            'metadata': followup_metadata,
        },
    }
    return await create_and_dispatch_task(
        workspace_id=wid,
        title=f'Prepare PR workspace #{context.pr_number}',
        prompt=f'Clone or refresh {context.repo_full_name} on branch {pr["head"]["ref"]} for PR fix execution.',
        agent_type='clone_repo',
        model_ref=MODEL_REF,
        metadata=metadata,
        task_timeout_seconds=DEFAULT_TASK_TIMEOUT,
        github_issue_url=github_issue_url,
        with_created=True,
    )
