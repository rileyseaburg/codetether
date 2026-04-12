"""Open-PR lookup helpers for issue-driven GitHub App runs."""

from .auth import github_json


async def open_issue_pr(repo_full_name: str, branch: str, token: str) -> dict | None:
    """Return the first open PR for the issue branch, if one exists."""
    owner = repo_full_name.split('/', 1)[0]
    pulls = await github_json(
        'GET',
        f'/repos/{repo_full_name}/pulls?head={owner}:{branch}&state=open',
        token,
    )
    return pulls[0] if pulls else None


def pr_state(pr: dict | None) -> tuple[int | None, str | None]:
    """Return the PR number and head SHA for change-detection checks."""
    head = (pr or {}).get('head') or {}
    return (pr or {}).get('number'), head.get('sha')
