"""Prompt construction for GitHub App-driven PR fixes."""

from .context import MentionContext


def _mergeability_line(pr: dict) -> str:
    """Summarize GitHub's current mergeability fields when available."""
    parts = []
    for key in ('mergeable', 'mergeable_state', 'mergeStateStatus'):
        value = pr.get(key)
        if value is not None:
            parts.append(f'{key}={value}')
    if not parts:
        return 'GitHub mergeability: not provided by webhook/API payload.'
    return 'GitHub mergeability: ' + ', '.join(parts) + '.'


def accepted_message(pr: dict) -> str:
    """Render the immediate acknowledgement comment for a PR fix request."""
    return (
        '## 🛠️ CodeTether Fix\n\n'
        f'Picked up this request for PR #{pr["number"]} on branch `{pr["head"]["ref"]}`. '
        "I'm preparing the workspace and will push changes directly to the existing PR branch if the task succeeds. "
        f'I will also make sure the branch is mergeable with `{pr["base"]["ref"]}`.'
    )


def fix_prompt(context: MentionContext, pr: dict) -> str:
    """Build the worker prompt for branch mutation on an existing PR."""
    path_line = (
        f'\nCommented file: {context.comment_path}'
        if context.comment_path
        else ''
    )
    hunk_line = (
        f'\nRelevant diff hunk:\n{context.comment_diff_hunk}'
        if context.comment_diff_hunk
        else ''
    )
    mergeability_line = _mergeability_line(pr)
    return f"""You are editing the existing PR branch for PR #{pr['number']}: "{pr['title']}" ({pr['head']['ref']} → {pr['base']['ref']}) in {context.repo_full_name}.

Apply the requested changes directly in the checked-out repository. Do not just describe the fix.

You are responsible for mergeability, not only the requested code change. Before completing:
- Fetch the latest base branch `{pr['base']['ref']}`.
- Merge or rebase the latest base into the existing PR branch `{pr['head']['ref']}`.
- If Git reports conflicts, resolve the conflict markers in the affected files, preserving the intended behavior from both the PR and base branch.
- Run `git status --short` and confirm there are no unresolved paths before committing.
- Run `git diff --check` before the final commit/push.

Do not abandon the task because the branch has merge conflicts. A successful PR task means the existing PR branch was pushed and should be mergeable with `{pr['base']['ref']}`. If conflict resolution is impossible, fail with a structured blocker list that includes the conflicted files, the exact commands attempted, and what context is needed to resume.

Do not stay in analysis mode. Use at most 5 discovery reads or searches before your first code edit. Prefer the files closest to the requested area, and keep moving toward an actual patch instead of repeating repo exploration.

{mergeability_line}

Triggering comment:
{context.comment_body}{path_line}{hunk_line}

After editing files, run the smallest relevant validation needed, commit the changes, and push them back to the existing PR branch `{pr['head']['ref']}`. Do not open a new PR. In the final response, include the commit SHA if you created one."""
