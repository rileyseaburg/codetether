"""Queue CodeTether work from GitHub App GitHub webhooks."""

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
    from .persistent_worker_pool import DEFAULT_TASK_TIMEOUT, create_and_dispatch_task

    branch, title, prompt, metadata = await _resolve_branch_and_prompt(event_name, payload)
    repo = payload['repository']
    installation_id = str(payload['installation']['id'])
    workspace_id = await _ensure_workspace(repo, installation_id, branch)
    task_id = await create_and_dispatch_task(
        workspace_id=workspace_id,
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
        task_timeout_seconds=DEFAULT_TASK_TIMEOUT,
    )
    return {'workspace_id': workspace_id, 'task_id': task_id, 'branch': branch}



FAILED_CHECK_CONCLUSIONS = {
    'action_required',
    'cancelled',
    'failure',
    'startup_failure',
    'timed_out',
}


def _first_pull_request_from_check(payload: Dict[str, Any]) -> Dict[str, Any] | None:
    check = payload.get('check_run') or payload.get('check_suite') or payload.get('workflow_run') or {}
    pull_requests = check.get('pull_requests') or payload.get('pull_requests') or []
    if pull_requests:
        return pull_requests[0]
    return None


def _check_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    return payload.get('check_run') or payload.get('check_suite') or payload.get('workflow_run') or {}


def should_queue_check_failure_task(event_name: str, payload: Dict[str, Any]) -> bool:
    """Return true when a GitHub check failure should spawn remediation work."""
    if event_name not in {'check_run', 'check_suite', 'workflow_run'}:
        return False
    if payload.get('action') not in {None, 'completed', 'requested_action'}:
        return False
    check = _check_payload(payload)
    conclusion = str(check.get('conclusion') or '').lower()
    if conclusion not in FAILED_CHECK_CONCLUSIONS:
        return False
    name = str(check.get('name') or check.get('check_suite', {}).get('app', {}).get('name') or '')
    app_slug = str((check.get('app') or {}).get('slug') or '').lower()
    app_name = str((check.get('app') or {}).get('name') or '').lower()
    # Avoid recursive loops where a failing CodeTether-created Check Run spawns itself.
    if name.lower().startswith('codetether /') or app_slug == bot_login().lower() or app_name == bot_login().lower():
        return False
    return _first_pull_request_from_check(payload) is not None


async def _fetch_pull_request_for_check(payload: Dict[str, Any]) -> Dict[str, Any]:
    repo = payload['repository']
    installation_id = str(payload['installation']['id'])
    pr = _first_pull_request_from_check(payload)
    if not pr:
        raise ValueError('check failure payload did not include a pull request')
    pr_url = pr.get('url') or f"https://api.github.com/repos/{repo['full_name']}/pulls/{pr['number']}"
    return (
        await github_installation_request(
            installation_id=installation_id,
            owner=repo['owner']['login'],
            repo=repo['name'],
            method='GET',
            url=pr_url,
        )
    ).json()


def _check_failure_prompt(event_name: str, payload: Dict[str, Any], pr: Dict[str, Any]) -> tuple[str, str, Dict[str, Any]]:
    check = _check_payload(payload)
    repo = payload['repository']
    installation_id = str(payload['installation']['id'])
    pr_number = int(pr['number'])
    branch = str(pr['head']['ref'])
    check_name = str(check.get('name') or check.get('app', {}).get('name') or event_name)
    conclusion = str(check.get('conclusion') or '')
    details_url = str(check.get('details_url') or check.get('html_url') or check.get('url') or '')
    head_sha = str(check.get('head_sha') or pr.get('head', {}).get('sha') or '')
    title = f"Fix failing PR #{pr_number} check: {check_name}"
    metadata: Dict[str, Any] = {
        'source': 'github_check_failure_webhook',
        'github_event': event_name,
        'github_repository': repo['full_name'],
        'github_installation_id': installation_id,
        'pr_number': pr_number,
        'check_name': check_name,
        'check_conclusion': conclusion,
        'check_details_url': details_url,
        'check_run_id': check.get('id'),
        'check_head_sha': head_sha,
        'source_metadata': {
            'actor_type': 'github_app',
            'service_account': f'github-app:{installation_id}',
            'repository': repo['full_name'],
            'trigger': 'failed_check',
        },
    }
    if target_agent_name():
        metadata['target_agent_name'] = target_agent_name()
    prompt = (
        f"A required PR check failed on {repo['full_name']} PR #{pr_number}: {pr.get('html_url')}\n\n"
        f"Branch: {branch}\n"
        f"Head SHA: {pr.get('head', {}).get('sha') or head_sha}\n"
        f"Check: {check_name}\n"
        f"Conclusion: {conclusion}\n"
        f"Details URL: {details_url or '(none)'}\n\n"
        "Investigate the failing check logs, make the smallest appropriate fix on the PR branch, "
        "commit and push to that same branch, then comment on the PR with the fix summary and validation evidence. "
        "Do not merge the PR; leave merge to the auto-merge gate once checks are green."
    )
    return title, prompt, metadata


async def queue_github_check_failure_task(event_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Queue a remediation session for a failed GitHub check on an open PR."""
    from .persistent_worker_pool import DEFAULT_TASK_TIMEOUT, create_and_dispatch_task

    repo = payload['repository']
    installation_id = str(payload['installation']['id'])
    pr = await _fetch_pull_request_for_check(payload)
    branch = str(pr['head']['ref'])
    title, prompt, metadata = _check_failure_prompt(event_name, payload, pr)
    workspace_id = await _ensure_workspace(repo, installation_id, branch)
    task_id = await create_and_dispatch_task(
        workspace_id=workspace_id,
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
        task_timeout_seconds=DEFAULT_TASK_TIMEOUT,
        github_issue_url=pr.get('html_url'),
    )
    return {
        'workspace_id': workspace_id,
        'task_id': task_id,
        'branch': branch,
        'pr_number': pr['number'],
        'check_name': metadata['check_name'],
    }
