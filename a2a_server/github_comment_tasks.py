"""Queue CodeTether work from GitHub App comment webhooks."""

from __future__ import annotations

import hashlib
import os
from typing import Any, Dict, Tuple

from . import database as db
from .git_service import default_clone_dir, store_git_credential_record
from .github_app_auth import github_app_id, github_installation_request


def bot_login() -> str:
    return os.environ.get('GITHUB_APP_BOT_LOGIN', 'codetether').strip() or 'codetether'


def target_agent_name() -> str | None:
    value = os.environ.get('GITHUB_APP_TARGET_AGENT', '').strip()
    return value or None


def has_bot_mention(body: str) -> bool:
    return f'@{bot_login()}'.lower() in (body or '').lower()


def workspace_id_for_repo(git_url: str) -> str:
    return hashlib.sha256(git_url.encode()).hexdigest()[:16]


async def _ensure_workspace(repo: Dict[str, Any], installation_id: str, branch: str) -> str:
    from .monitor_api import get_agent_bridge

    git_url = repo['clone_url']
    workspace_id = workspace_id_for_repo(git_url)
    agent_config = {
        'git_auth': {
            'type': 'github_app',
            'github_app': {
                'installation_id': installation_id,
                'owner': repo['owner']['login'],
                'repo': repo['name'],
                'app_id': github_app_id(),
            },
        }
    }
    await store_git_credential_record(
        workspace_id,
        {
            'token_type': 'github_app',
            'github_installation_id': installation_id,
            'github_owner': repo['owner']['login'],
            'github_repo': repo['name'],
            'github_app_id': github_app_id(),
            'git_url': git_url,
        },
    )
    workspace = {
        'id': workspace_id,
        'name': repo['full_name'],
        'path': default_clone_dir(workspace_id),
        'description': f"GitHub App workspace for {repo['full_name']}",
        'agent_config': agent_config,
        'git_url': git_url,
        'git_branch': branch,
        'status': 'cloning',
    }
    await db.db_upsert_workspace(workspace)
    bridge = get_agent_bridge()
    if bridge is not None:
        await bridge.register_workspace(
            name=workspace['name'],
            path=workspace['path'],
            description=workspace['description'],
            agent_config=agent_config,
            workspace_id=workspace_id,
        )
    return workspace_id


async def _resolve_branch_and_prompt(event_name: str, payload: Dict[str, Any]) -> Tuple[str, str, str, Dict[str, Any]]:
    comment = payload['comment']
    repo = payload['repository']
    installation_id = str(payload['installation']['id'])
    metadata = {
        'source': 'github_webhook',
        'github_event': event_name,
        'github_repository': repo['full_name'],
        'github_installation_id': installation_id,
        'source_metadata': {
            'actor_type': 'github_app',
            'service_account': f'github-app:{installation_id}',
            'repository': repo['full_name'],
        },
    }
    if target_agent_name():
        metadata['target_agent_name'] = target_agent_name()
    if event_name == 'pull_request_review_comment':
        pr = payload['pull_request']
        metadata['pr_number'] = pr['number']
        metadata['comment_id'] = comment['id']
        return (
            pr['head']['ref'],
            f"Address PR #{pr['number']} comment",
            (
                f"You were mentioned in review comment {comment['html_url']} on PR #{pr['number']}.\n\n"
                f"Pull request title: {pr['title']}\n\nComment:\n{comment['body']}\n\n"
                "Address the request on the PR branch, commit the fix, push it, and update or create the PR as needed."
            ),
            metadata,
        )

    issue = payload['issue']
    metadata['issue_number'] = issue['number']
    metadata['comment_id'] = comment['id']
    pr_ref = issue.get('pull_request', {}).get('url')
    if pr_ref:
        pr = (
            await github_installation_request(
                installation_id=installation_id,
                owner=repo['owner']['login'],
                repo=repo['name'],
                method='GET',
                url=pr_ref,
            )
        ).json()
        metadata['pr_number'] = pr['number']
        return (
            pr['head']['ref'],
            f"Address PR #{pr['number']} mention",
            (
                f"You were mentioned in issue comment {comment['html_url']} on PR #{pr['number']}.\n\n"
                f"Pull request title: {pr['title']}\n\nComment:\n{comment['body']}\n\n"
                "Address the request on the PR branch, commit the fix, push it, and update the PR."
            ),
            metadata,
        )

    return (
        repo.get('default_branch') or 'main',
        f"Resolve issue #{issue['number']}: {issue['title']}",
        (
            f"You were mentioned on issue #{issue['number']} ({issue['html_url']}).\n\n"
            f"Issue title: {issue['title']}\n\nIssue body:\n{issue.get('body') or '(none)'}\n\n"
            f"Comment:\n{comment['body']}\n\n"
            "Implement the requested change, commit it on a new branch, push the branch, and open or update a PR that references the issue."
        ),
        metadata,
    )


async def queue_github_comment_task(event_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    from .monitor_api import get_agent_bridge

    branch, title, prompt, metadata = await _resolve_branch_and_prompt(event_name, payload)
    repo = payload['repository']
    installation_id = str(payload['installation']['id'])
    workspace_id = await _ensure_workspace(repo, installation_id, branch)
    bridge = get_agent_bridge()
    if bridge is None:
        raise RuntimeError('Agent bridge not available')
    task = await bridge.create_task(
        codebase_id=workspace_id,
        title=f"Prepare repository: {repo['full_name']}",
        prompt=f"Clone or update {repo['full_name']} at branch {branch}",
        agent_type='clone_repo',
        metadata={
            'git_url': repo['clone_url'],
            'git_branch': branch,
            'workspace_id': workspace_id,
            'post_clone_task': {
                'title': title,
                'prompt': prompt,
                'agent_type': 'build',
                'metadata': metadata,
            },
        },
    )
    if task is None:
        raise RuntimeError('Failed to queue repository preparation task')
    return {'workspace_id': workspace_id, 'task_id': task.id, 'branch': branch}
