import pytest

from a2a_server.github_app import handler
from a2a_server.github_app.context import MentionContext


@pytest.mark.asyncio
async def test_issue_fix_request_skips_when_issue_branch_pr_already_open(
    monkeypatch,
):
    calls = []

    context = MentionContext(
        repo_full_name='owner/repo',
        installation_id=123,
        issue_number=42,
        pr_number=None,
        comment_id=99,
        comment_body='@codetether handle this issue',
    )

    async def fake_github_json(method, path, token, payload=None):
        calls.append(('github_json', method, path))
        if path == '/repos/owner/repo':
            return {
                'clone_url': 'https://github.com/owner/repo.git',
                'default_branch': 'main',
            }
        if path == '/repos/owner/repo/git/ref/heads/main':
            return {'object': {'sha': 'base-sha'}}
        if path == '/repos/owner/repo/issues/42':
            return {
                'id': 42,
                'number': 42,
                'title': 'Old issue',
                'body': '@codetether handle this issue',
            }
        raise AssertionError(f'unexpected GitHub API path: {path}')

    async def fake_open_issue_pr(repo, branch, token):
        calls.append(('open_issue_pr', repo, branch))
        assert repo == 'owner/repo'
        assert branch == 'codetether/issue-42'
        return {
            'number': 100,
            'html_url': 'https://github.com/owner/repo/pull/100',
        }

    async def fake_post_issue_comment(repo, issue_number, token, body):
        calls.append(('post_issue_comment', repo, issue_number, body))

    async def fail_create_issue_clone_task(*args, **kwargs):
        raise AssertionError(
            'existing issue PR must prevent duplicate task creation',
        )

    monkeypatch.setattr(handler, 'github_json', fake_github_json)
    monkeypatch.setattr(handler, 'open_issue_pr', fake_open_issue_pr)
    monkeypatch.setattr(handler, 'post_issue_comment', fake_post_issue_comment)
    monkeypatch.setattr(
        handler,
        'create_issue_clone_task',
        fail_create_issue_clone_task,
    )

    result = await handler.handle_fix_request(context, 'ghs_test')

    assert result == {
        'accepted': False,
        'reason': 'open-issue-pr-exists',
        'pr_number': 100,
        'pr_url': 'https://github.com/owner/repo/pull/100',
    }
    assert ('open_issue_pr', 'owner/repo', 'codetether/issue-42') in calls
    assert any(
        call[0] == 'post_issue_comment' and 'existing open PR' in call[3]
        for call in calls
    )
