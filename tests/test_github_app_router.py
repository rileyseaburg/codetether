import json

import pytest

from a2a_server.github_app import router


@pytest.mark.asyncio
async def test_non_fix_mention_posts_actionable_issue_and_pr_guidance(monkeypatch):
    calls = []

    class FakeRequest:
        headers = {
            'X-Hub-Signature-256': 'sha256=test',
            'X-GitHub-Event': 'issue_comment',
        }

        async def body(self):
            return json.dumps({
                'action': 'created',
                'installation': {'id': 123},
                'repository': {'full_name': 'owner/repo'},
                'issue': {'number': 7},
                'comment': {'id': 99, 'body': '@codetether thanks for looking'},
            }).encode()

    async def fake_verify(signature, body):
        assert signature == 'sha256=test'

    async def fake_installation_token(installation_id):
        assert installation_id == 123
        return 'ghs_test', '2026-04-24T22:00:00Z'

    async def fake_post_issue_comment(repo, issue_number, token, body):
        calls.append((repo, issue_number, token, body))

    monkeypatch.setattr(router, 'verify_signature', fake_verify)
    monkeypatch.setattr(router, 'installation_token', fake_installation_token)
    monkeypatch.setattr(router, 'post_issue_comment', fake_post_issue_comment)

    result = await router.handle_github_webhook(FakeRequest())

    assert result == {'accepted': False, 'reason': 'non-fix mention'}
    assert calls
    repo, issue_number, token, body = calls[0]
    assert repo == 'owner/repo'
    assert issue_number == 7
    assert token == 'ghs_test'
    assert 'I only start repository-changing work' in body
    assert 'For issues, I can create a branch and open a PR' in body
    assert 'for pull requests, I can push to the PR branch' in body
    assert '@codetether handle this issue' in body
    assert '@codetether implement this' in body
    assert 'only mutate PR branches' not in body
