"""Prompt helpers for GitHub App issue automation."""

from .context import MentionContext


def issue_branch(context: MentionContext) -> str:
    """Return the deterministic branch name used for issue fixes."""
    return f'codetether/issue-{context.issue_number}'


def accepted_issue_message(issue: dict, branch: str) -> str:
    """Render the acknowledgement comment for an issue fix request."""
    return (
        "## 🛠️ CodeTether Fix\n\n"
        f"Picked up issue #{issue['number']} on branch `{branch}`. "
        "I’m preparing the workspace and will open a PR if the task succeeds."
    )


def issue_fix_prompt(
    context: MentionContext, issue: dict, repo: dict, branch: str
) -> str:
    """Build the worker prompt for an issue-driven branch and PR."""
    body = issue.get('body') or 'No issue description was provided.'
    return f"""You are implementing issue #{issue['number']}: "{issue['title']}" in {context.repo_full_name}.

Work from the checked-out repository, create or reuse branch `{branch}`, apply the requested changes, run the smallest relevant validation, commit, push, and open a pull request against `{repo['default_branch']}`.

Issue description:
{body}

Triggering comment:
{context.comment_body}

In the final response, include the commit SHA and PR URL if you created them."""
