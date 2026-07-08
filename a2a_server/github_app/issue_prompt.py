"""Prompt helpers for GitHub App issue automation."""

from .context import MentionContext


def issue_branch(context: MentionContext) -> str:
    """Return the deterministic branch name used for issue fixes."""
    return f'codetether/issue-{context.issue_number}'


def accepted_issue_message(issue: dict, branch: str) -> str:
    """Render the acknowledgement comment for an issue fix request."""
    return (
        '## 🛠️ CodeTether Fix\n\n'
        f'Picked up issue #{issue["number"]} on branch `{branch}`. '
        'I’m preparing the workspace and will open a PR if the task succeeds.'
    )


def issue_fix_prompt(
    context: MentionContext, issue: dict, repo: dict, branch: str
) -> str:
    """Build the worker prompt for an issue-driven branch and PR."""
    body = issue.get('body') or 'No issue description was provided.'
    return f"""You are implementing issue #{issue['number']}: "{issue['title']}" in {context.repo_full_name}.

Work from the checked-out repository, create or reuse branch `{branch}`, apply the requested changes, run the smallest relevant validation, commit, push, and open a pull request against `{repo['default_branch']}`.

When opening the pull request, write a Forgejo-facing pull request body as real multiline Markdown with these sections in this order:

```markdown
## Summary
- Concise bullet describing the user-visible change.
- Concise bullet describing the implementation scope.

## Validation
- validation-level: exact command/result or explicit blocker.

## CodeTether provenance
- Issue: #{issue['number']}
- Branch: `{branch}`
- Base: `{repo['default_branch']}`
- Reviewer/merge-steward agents will enforce policy gates.
```

Do not flatten the PR body into one paragraph. Do not encode newline characters as literal `\\n`; pass real newline characters to the Forgejo pull request API or CLI. Use CodeTether's concise, provenance-aware personality/avatar in Forgejo-facing text.

Do not stay in analysis mode. Use at most 5 discovery reads or searches before your first code edit. Prefer editing the most obvious matching files first, especially files whose names or paths match the requested feature area. If a transient provider or network error occurs, continue and finish the implementation instead of restarting the task from scratch.

Issue description:
{body}

Triggering comment:
{context.comment_body}

In the final response, include the commit SHA and PR URL if you created them."""
