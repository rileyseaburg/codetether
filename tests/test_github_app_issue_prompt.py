from a2a_server.github_app.context import MentionContext
from a2a_server.github_app.issue_prompt import issue_fix_prompt


def _issue_context() -> MentionContext:
    return MentionContext(
        repo_full_name='owner/repo',
        installation_id=123,
        issue_number=3815,
        pr_number=None,
        comment_id=77,
        comment_body='@codetether implement the requested feature',
    )


def test_issue_fix_prompt_requires_multiline_forgejo_pr_body():
    prompt = issue_fix_prompt(
        _issue_context(),
        {
            'number': 3815,
            'title': 'Retargeting visitors',
            'body': 'Add visitors to the retargeting status UI.',
        },
        {'default_branch': 'main'},
        'codetether/issue-3815',
    )

    assert 'Forgejo-facing pull request body' in prompt
    assert '## Summary' in prompt
    assert '## Validation' in prompt
    assert '## CodeTether provenance' in prompt
    assert 'Do not flatten the PR body into one paragraph' in prompt
    assert 'real newline characters' in prompt
