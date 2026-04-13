"""Prompt construction for GitHub App-driven PR fixes."""

from .context import MentionContext


def accepted_message(pr: dict) -> str:
    """Render the immediate acknowledgement comment for a PR fix request."""
    return (
        "## 🛠️ CodeTether Fix\n\n"
        f"Picked up this request for PR #{pr['number']} on branch `{pr['head']['ref']}`. "
        "I’m preparing the workspace and will push changes directly to the existing PR branch if the task succeeds."
    )


def fix_prompt(context: MentionContext, pr: dict) -> str:
    """Build the worker prompt for branch mutation on an existing PR."""
    path_line = f"\nCommented file: {context.comment_path}" if context.comment_path else ''
    hunk_line = f"\nRelevant diff hunk:\n{context.comment_diff_hunk}" if context.comment_diff_hunk else ''
    return f"""You are editing the existing PR branch for PR #{pr['number']}: "{pr['title']}" ({pr['head']['ref']} → {pr['base']['ref']}) in {context.repo_full_name}.

Apply the requested changes directly in the checked-out repository. Do not just describe the fix.

Triggering comment:
{context.comment_body}{path_line}{hunk_line}

After editing files, run the smallest relevant validation needed, commit the changes, and push them back to the existing PR branch `{pr['head']['ref']}`. Do not open a new PR. In the final response, include the commit SHA if you created one."""
