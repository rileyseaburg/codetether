"""Request dispatch for GitHub App fix comments.

Entry point: POST /v1/webhooks/github → handle_fix_request().

This is fire-and-forget: we create the clone task with fire-and-forget
semantics, post an acceptance comment, and return immediately. No GitHub Action
is involved; the persistent worker (harvester) picks up tasks from our compute
cluster.

Task lifecycle:
  1. handle_fix_request() → create_and_dispatch_task() (fire-and-forget)
  2. Persistent worker claims task via SSE notification
  3. Clone completes → pr/issue_prepare_completion creates build task
  4. Build completes → pr/issue_final_comment posts result
  5. github_progress_service posts comments every 5 min while running
  6. task_reaper detects silent workers, requeues from checkpoint
"""

from a2a_server.github_app.auth import github_json
from a2a_server.github_app.context import MentionContext
from a2a_server.github_app.issue_clone_task import create_issue_clone_task
from a2a_server.github_app.issue_pr import open_issue_pr
from a2a_server.github_app.issue_prompt import (
    accepted_issue_message,
    issue_branch,
)
from a2a_server.github_app.prompt import accepted_message
from a2a_server.github_app.watch import post_issue_comment
from a2a_server.github_app.workspace import create_clone_task, ensure_workspace


def _build_github_issue_url(
    repo_full_name: str,
    issue_number: int,
    pr_number: int | None,
) -> str:
    """Construct the GitHub issue/PR URL for progress reporter."""
    if pr_number:
        return f'https://github.com/{repo_full_name}/pull/{pr_number}'
    return f'https://github.com/{repo_full_name}/issues/{issue_number}'


async def _handle_pr_fix_request(
    context: MentionContext,
    token: str,
    github_issue_url: str,
) -> dict:
    pr = await github_json(
        'GET',
        f'/repos/{context.repo_full_name}/pulls/{context.pr_number}',
        token,
    )
    if pr['head']['repo']['full_name'] != context.repo_full_name:
        await post_issue_comment(
            context.repo_full_name,
            context.issue_number,
            token,
            "## 🛠️ CodeTether Fix\n\n"
            'Auto-fix is not available for forked pull requests because I '
            f"cannot safely push to `{pr['head']['repo']['full_name']}:"
            f"{pr['head']['ref']}`.",
        )
        return {'accepted': False, 'reason': 'forked-pr'}
    wid = await ensure_workspace(context, pr)
    clone_task_id, created = await create_clone_task(
        context,
        pr,
        wid,
        github_issue_url=github_issue_url,
        github_installation_id=context.installation_id,
    )
    if created:
        await post_issue_comment(
            context.repo_full_name,
            context.issue_number,
            token,
            accepted_message(pr),
        )
    return {
        'accepted': True,
        'workspace_id': wid,
        'clone_task_id': clone_task_id,
        'created': created,
    }


async def _handle_issue_fix_request(
    context: MentionContext,
    token: str,
    github_issue_url: str,
) -> dict:
    repo = await github_json('GET', f'/repos/{context.repo_full_name}', token)
    base_ref = await github_json(
        'GET',
        f"/repos/{context.repo_full_name}/git/ref/heads/"
        f"{repo['default_branch']}",
        token,
    )
    issue = await github_json(
        'GET',
        f'/repos/{context.repo_full_name}/issues/{context.issue_number}',
        token,
    )
    branch = issue_branch(context)
    existing_pr = await open_issue_pr(context.repo_full_name, branch, token)
    if existing_pr:
        pr_url = existing_pr.get('html_url') or existing_pr.get('url')
        await post_issue_comment(
            context.repo_full_name,
            context.issue_number,
            token,
            "## 🛠️ CodeTether Fix\n\n"
            f'I found an existing open PR for issue #{context.issue_number}: '
            f"{pr_url}. I won't start another duplicate PR task for the "
            'same issue branch.',
        )
        return {
            'accepted': False,
            'reason': 'open-issue-pr-exists',
            'pr_number': existing_pr.get('number'),
            'pr_url': pr_url,
        }
    checkout = {
        'head': {
            'repo': {'clone_url': repo['clone_url']},
            'ref': branch,
        },
        'base': {'ref': repo['default_branch']},
    }
    wid = await ensure_workspace(context, checkout)
    clone_task_id, created = await create_issue_clone_task(
        context,
        issue,
        repo,
        wid,
        branch,
        github_issue_url=github_issue_url,
        github_installation_id=context.installation_id,
        github_check_head_sha=((base_ref.get('object') or {}).get('sha') or ''),
    )
    if created:
        await post_issue_comment(
            context.repo_full_name,
            context.issue_number,
            token,
            accepted_issue_message(issue, branch),
        )
    return {
        'accepted': True,
        'workspace_id': wid,
        'clone_task_id': clone_task_id,
        'created': created,
    }


async def handle_fix_request(context: MentionContext, token: str) -> dict:
    """Route a GitHub comment request into PR or issue automation."""
    github_issue_url = _build_github_issue_url(
        context.repo_full_name,
        context.issue_number,
        context.pr_number,
    )
    if context.pr_number:
        return await _handle_pr_fix_request(context, token, github_issue_url)
    return await _handle_issue_fix_request(context, token, github_issue_url)
