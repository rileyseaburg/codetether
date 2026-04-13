"""Request dispatch for GitHub App fix comments."""

import asyncio

from .auth import github_json
from .context import MentionContext
from .issue_clone_task import create_issue_clone_task
from .issue_prompt import accepted_issue_message, issue_branch
from .prompt import accepted_message
from .watch import monitor_pr_fix, post_issue_comment
from .workspace import create_clone_task, ensure_workspace


async def handle_fix_request(context: MentionContext, token: str) -> dict:
    """Route a GitHub comment request into the PR or plain-issue automation flow."""
    if context.pr_number:
        pr = await github_json('GET', f'/repos/{context.repo_full_name}/pulls/{context.pr_number}', token)
        if pr['head']['repo']['full_name'] != context.repo_full_name:
            await post_issue_comment(context.repo_full_name, context.issue_number, token, f"## 🛠️ CodeTether Fix\n\nAuto-fix is not available for forked pull requests because I cannot safely push to `{pr['head']['repo']['full_name']}:{pr['head']['ref']}`.")
            return {'accepted': False, 'reason': 'forked-pr'}
        wid = await ensure_workspace(context, pr)
        clone_task_id = await create_clone_task(context, pr, wid)
        await post_issue_comment(context.repo_full_name, context.issue_number, token, accepted_message(pr))
        asyncio.create_task(monitor_pr_fix(context, pr, clone_task_id, pr['head']['sha'], token))
        return {'accepted': True, 'workspace_id': wid, 'clone_task_id': clone_task_id}
    repo = await github_json('GET', f'/repos/{context.repo_full_name}', token)
    issue = await github_json('GET', f'/repos/{context.repo_full_name}/issues/{context.issue_number}', token)
    branch = issue_branch(context)
    checkout = {'head': {'repo': {'clone_url': repo['clone_url']}, 'ref': branch}, 'base': {'ref': repo['default_branch']}}
    wid = await ensure_workspace(context, checkout)
    clone_task_id = await create_issue_clone_task(context, issue, repo, wid, branch)
    await post_issue_comment(context.repo_full_name, context.issue_number, token, accepted_issue_message(issue, branch))
    return {'accepted': True, 'workspace_id': wid, 'clone_task_id': clone_task_id}
