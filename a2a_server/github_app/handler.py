"""Request dispatch for GitHub App fix comments.

Entry point: POST /v1/webhooks/github → handle_fix_request()

This is fire-and-forget: we create the clone task with dispatch_mode=fire_and_forget
and task_timeout_seconds=604800, post an acceptance comment, and return immediately.
No GitHub Action is involved — the persistent worker (harvester) picks up tasks
from our compute cluster.

Task lifecycle:
  1. handle_fix_request() → create_and_dispatch_task() (fire-and-forget)
  2. Persistent worker claims task via SSE notification
  3. Clone completes → pr/issue_prepare_completion creates build task
  4. Build completes → pr/issue_final_comment posts result
  5. github_progress_service posts comments every 5 min while running
  6. task_reaper detects silent workers, requeues from checkpoint
"""

from .auth import github_json
from .context import MentionContext
from .issue_clone_task import create_issue_clone_task
from .issue_prompt import accepted_issue_message, issue_branch
from .prompt import accepted_message
from .watch import post_issue_comment
from .workspace import create_clone_task, ensure_workspace


def _build_github_issue_url(repo_full_name: str, issue_number: int, pr_number: int | None) -> str:
    """Construct the GitHub issue/PR URL for progress reporter."""
    if pr_number:
        return f'https://github.com/{repo_full_name}/pull/{pr_number}'
    return f'https://github.com/{repo_full_name}/issues/{issue_number}'


async def handle_fix_request(context: MentionContext, token: str) -> dict:
    """Route a GitHub comment request into the PR or plain-issue automation flow.

    This is fire-and-forget: we create the clone task, post an acceptance
    comment, and return immediately. The task lifecycle is event-driven:
      - Clone completes → pr/issue_prepare_completion creates build task
      - Build completes → pr/issue_final_comment posts result
      - Progress reported by github_progress_service every 5 min
      - Worker death detected by task_reaper → requeue or fail with comment
    """
    github_issue_url = _build_github_issue_url(
        context.repo_full_name, context.issue_number, context.pr_number
    )

    if context.pr_number:
        pr = await github_json('GET', f'/repos/{context.repo_full_name}/pulls/{context.pr_number}', token)
        if pr['head']['repo']['full_name'] != context.repo_full_name:
            await post_issue_comment(context.repo_full_name, context.issue_number, token, f"## 🛠️ CodeTether Fix\n\nAuto-fix is not available for forked pull requests because I cannot safely push to `{pr['head']['repo']['full_name']}:{pr['head']['ref']}`.")
            return {'accepted': False, 'reason': 'forked-pr'}
        wid = await ensure_workspace(context, pr)
        clone_task_id = await create_clone_task(
            context, pr, wid,
            github_issue_url=github_issue_url,
            github_installation_id=context.installation_id,
        )
        await post_issue_comment(context.repo_full_name, context.issue_number, token, accepted_message(pr))
        return {'accepted': True, 'workspace_id': wid, 'clone_task_id': clone_task_id}

    repo = await github_json('GET', f'/repos/{context.repo_full_name}', token)
    base_ref = await github_json(
        'GET',
        f"/repos/{context.repo_full_name}/git/ref/heads/{repo['default_branch']}",
        token,
    )
    issue = await github_json('GET', f'/repos/{context.repo_full_name}/issues/{context.issue_number}', token)
    branch = issue_branch(context)
    checkout = {'head': {'repo': {'clone_url': repo['clone_url']}, 'ref': branch}, 'base': {'ref': repo['default_branch']}}
    wid = await ensure_workspace(context, checkout)
    clone_task_id = await create_issue_clone_task(
        context, issue, repo, wid, branch,
        github_issue_url=github_issue_url,
        github_installation_id=context.installation_id,
        github_check_head_sha=((base_ref.get('object') or {}).get('sha') or ''),
    )
    await post_issue_comment(context.repo_full_name, context.issue_number, token, accepted_issue_message(issue, branch))
    return {'accepted': True, 'workspace_id': wid, 'clone_task_id': clone_task_id}
