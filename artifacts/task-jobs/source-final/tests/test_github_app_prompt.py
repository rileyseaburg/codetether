from a2a_server.github_app.context import MentionContext
from a2a_server.github_app.prompt import accepted_message, fix_prompt


def _context() -> MentionContext:
    return MentionContext(
        repo_full_name='owner/repo',
        installation_id=123,
        issue_number=9,
        pr_number=9,
        comment_id=77,
        comment_body='@codetether this is not mergeable, please fix',
    )


def _pr() -> dict:
    return {
        'number': 9,
        'title': 'Feature branch',
        'mergeable': False,
        'mergeable_state': 'dirty',
        'head': {'ref': 'feature/example'},
        'base': {'ref': 'main'},
    }


def test_pr_acceptance_message_commits_to_mergeability_work():
    message = accepted_message(_pr())

    assert 'feature/example' in message
    assert 'mergeable with `main`' in message


def test_pr_fix_prompt_requires_conflict_resolution_before_completion():
    prompt = fix_prompt(_context(), _pr())

    assert 'GitHub mergeability: mergeable=False, mergeable_state=dirty.' in prompt
    assert 'Fetch the latest base branch `main`' in prompt
    assert 'resolve the conflict markers' in prompt
    assert 'git status --short' in prompt
    assert 'git diff --check' in prompt
    assert 'structured blocker list' in prompt
    assert 'existing PR branch `feature/example`' in prompt
