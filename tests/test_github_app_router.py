import json

import pytest

from a2a_server.github_app import router


@pytest.mark.asyncio
async def test_non_fix_mention_posts_actionable_issue_and_pr_guidance(
    monkeypatch,
):
    calls = []
    app_slug = router.APP_SLUG

    class FakeRequest:
        headers = {
            'X-Hub-Signature-256': 'sha256=test',
            'X-GitHub-Event': 'issue_comment',
        }

        async def body(self):
            return json.dumps(
                {
                    'action': 'created',
                    'installation': {'id': 123},
                    'repository': {'full_name': 'owner/repo'},
                    'issue': {'number': 7},
                    'comment': {
                        'id': 99,
                        'body': f'@{app_slug} thanks for looking',
                    },
                }
            ).encode()

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
    assert f'@{app_slug} handle this issue' in body
    assert f'@{app_slug} implement this' in body
    assert 'only mutate PR branches' not in body


@pytest.mark.asyncio
async def test_build_failed_mention_routes_to_fix_handler(monkeypatch):
    calls = []
    app_slug = router.APP_SLUG

    class FakeRequest:
        headers = {
            'X-Hub-Signature-256': 'sha256=test',
            'X-GitHub-Event': 'issue_comment',
        }

        async def body(self):
            return json.dumps(
                {
                    'action': 'created',
                    'installation': {'id': 123},
                    'repository': {'full_name': 'owner/repo'},
                    'issue': {
                        'number': 87,
                        'pull_request': {
                            'url': 'https://api.github.com/repos/owner/repo/pulls/87'
                        },
                    },
                    'comment': {
                        'id': 99,
                        'body': f'@{app_slug} the build failed',
                    },
                }
            ).encode()

    async def fake_verify(signature, body):
        assert signature == 'sha256=test'

    async def fake_installation_token(installation_id):
        assert installation_id == 123
        return 'ghs_test', '2026-04-24T22:00:00Z'

    async def fake_handle_fix_request(context, token):
        calls.append((context, token))
        return {'accepted': True, 'clone_task_id': 'task-build-failed'}

    async def fail_post_issue_comment(*args, **kwargs):
        raise AssertionError(
            'build failed mention should not get non-fix guidance'
        )

    monkeypatch.setattr(router, 'verify_signature', fake_verify)
    monkeypatch.setattr(router, 'installation_token', fake_installation_token)
    monkeypatch.setattr(router, 'handle_fix_request', fake_handle_fix_request)
    monkeypatch.setattr(router, 'post_issue_comment', fail_post_issue_comment)

    result = await router.handle_github_webhook(FakeRequest())

    assert result == {'accepted': True, 'clone_task_id': 'task-build-failed'}
    assert calls
    context, token = calls[0]
    assert token == 'ghs_test'
    assert context.repo_full_name == 'owner/repo'
    assert context.issue_number == 87
    assert context.comment_body == f'@{app_slug} the build failed'


@pytest.mark.asyncio
async def test_bot_authored_issue_comment_is_ignored(monkeypatch):
    app_slug = router.APP_SLUG

    class FakeRequest:
        headers = {
            'X-Hub-Signature-256': 'sha256=test',
            'X-GitHub-Event': 'issue_comment',
        }

        async def body(self):
            return json.dumps(
                {
                    'action': 'created',
                    'installation': {'id': 123},
                    'repository': {'full_name': 'owner/repo'},
                    'sender': {'login': f'{app_slug}[bot]', 'type': 'Bot'},
                    'issue': {'number': 7},
                    'comment': {
                        'id': 99,
                        'user': {'login': f'{app_slug}[bot]', 'type': 'Bot'},
                        'body': f'@{app_slug} follow-up required: please address tests',
                    },
                }
            ).encode()

    async def fake_verify(signature, body):
        assert signature == 'sha256=test'

    async def fail_installation_token(installation_id):
        raise AssertionError(
            'installation token should not be minted for bot-authored comments'
        )

    async def fail_handle_fix_request(context, token):
        raise AssertionError('bot-authored comments must not create fix tasks')

    monkeypatch.setattr(router, 'verify_signature', fake_verify)
    monkeypatch.setattr(router, 'installation_token', fail_installation_token)
    monkeypatch.setattr(router, 'handle_fix_request', fail_handle_fix_request)

    result = await router.handle_github_webhook(FakeRequest())

    assert result == {
        'ignored': True,
        'reason': 'self-authored-event',
        'event': 'issue_comment',
        'action': 'created',
    }


@pytest.mark.asyncio
async def test_issue_opened_mention_routes_to_fix_handler(monkeypatch):
    calls = []
    app_slug = router.APP_SLUG

    class FakeRequest:
        headers = {
            'X-Hub-Signature-256': 'sha256=test',
            'X-GitHub-Event': 'issues',
        }

        async def body(self):
            return json.dumps(
                {
                    'action': 'opened',
                    'installation': {'id': 123},
                    'repository': {'full_name': 'owner/repo'},
                    'issue': {
                        'id': 456,
                        'number': 7,
                        'title': 'Broken flow',
                        'body': f'@{app_slug} handle this issue',
                    },
                }
            ).encode()

    async def fake_verify(signature, body):
        assert signature == 'sha256=test'

    async def fake_installation_token(installation_id):
        assert installation_id == 123
        return 'ghs_test', '2026-04-24T22:00:00Z'

    async def fake_handle_fix_request(context, token):
        calls.append((context, token))
        return {'accepted': True, 'clone_task_id': 'task-1'}

    monkeypatch.setattr(router, 'verify_signature', fake_verify)
    monkeypatch.setattr(router, 'installation_token', fake_installation_token)
    monkeypatch.setattr(router, 'handle_fix_request', fake_handle_fix_request)

    result = await router.handle_github_webhook(FakeRequest())

    assert result == {'accepted': True, 'clone_task_id': 'task-1'}
    assert calls
    context, token = calls[0]
    assert token == 'ghs_test'
    assert context.repo_full_name == 'owner/repo'
    assert context.issue_number == 7
    assert context.pr_number is None
    assert context.comment_id == 456
    assert context.comment_body == f'@{app_slug} handle this issue'


@pytest.mark.asyncio
async def test_issue_edited_ignores_existing_mentions(monkeypatch):
    app_slug = router.APP_SLUG

    class FakeRequest:
        headers = {
            'X-Hub-Signature-256': 'sha256=test',
            'X-GitHub-Event': 'issues',
        }

        async def body(self):
            return json.dumps(
                {
                    'action': 'edited',
                    'changes': {'body': {'from': f'@{app_slug} old request'}},
                    'installation': {'id': 123},
                    'repository': {'full_name': 'owner/repo'},
                    'issue': {
                        'id': 456,
                        'number': 7,
                        'body': f'@{app_slug} handle this issue',
                    },
                }
            ).encode()

    async def fake_verify(signature, body):
        assert signature == 'sha256=test'

    async def fail_installation_token(installation_id):
        raise AssertionError('installation token should not be minted')

    monkeypatch.setattr(router, 'verify_signature', fake_verify)
    monkeypatch.setattr(router, 'installation_token', fail_installation_token)

    result = await router.handle_github_webhook(FakeRequest())

    assert result == {
        'ignored': True,
        'reason': 'unsupported-event-action',
        'event': 'issues',
        'action': 'edited',
    }


@pytest.mark.asyncio
async def test_self_authored_issue_comment_is_ignored(monkeypatch):
    app_slug = router.APP_SLUG

    class FakeRequest:
        headers = {
            'X-Hub-Signature-256': 'sha256=test',
            'X-GitHub-Event': 'issue_comment',
        }

        async def body(self):
            return json.dumps(
                {
                    'action': 'created',
                    'sender': {'login': f'{app_slug}[bot]', 'type': 'Bot'},
                    'installation': {'id': 123},
                    'repository': {'full_name': 'owner/repo'},
                    'issue': {'number': 7},
                    'comment': {
                        'id': 99,
                        'body': f'Try `@{app_slug} handle this issue`.',
                        'user': {'login': f'{app_slug}[bot]', 'type': 'Bot'},
                    },
                }
            ).encode()

    async def fake_verify(signature, body):
        assert signature == 'sha256=test'

    async def fail_installation_token(installation_id):
        raise AssertionError('installation token should not be minted')

    async def fail_handle_fix_request(context, token):
        raise AssertionError('self-authored comments should not create tasks')

    monkeypatch.setattr(router, 'verify_signature', fake_verify)
    monkeypatch.setattr(router, 'installation_token', fail_installation_token)
    monkeypatch.setattr(router, 'handle_fix_request', fail_handle_fix_request)

    result = await router.handle_github_webhook(FakeRequest())

    assert result == {
        'ignored': True,
        'reason': 'self-authored-event',
        'event': 'issue_comment',
        'action': 'created',
    }


@pytest.mark.asyncio
async def test_self_authored_review_comment_is_ignored(monkeypatch):
    app_slug = router.APP_SLUG

    class FakeRequest:
        headers = {
            'X-Hub-Signature-256': 'sha256=test',
            'X-GitHub-Event': 'pull_request_review_comment',
        }

        async def body(self):
            return json.dumps(
                {
                    'action': 'created',
                    'sender': {'login': f'{app_slug}[bot]', 'type': 'Bot'},
                    'installation': {'id': 123},
                    'repository': {'full_name': 'owner/repo'},
                    'pull_request': {'number': 7},
                    'comment': {
                        'id': 99,
                        'body': f'@{app_slug} finish this',
                        'path': 'app.py',
                        'diff_hunk': '@@',
                        'user': {'login': f'{app_slug}[bot]', 'type': 'Bot'},
                    },
                }
            ).encode()

    async def fake_verify(signature, body):
        assert signature == 'sha256=test'

    async def fail_installation_token(installation_id):
        raise AssertionError('installation token should not be minted')

    monkeypatch.setattr(router, 'verify_signature', fake_verify)
    monkeypatch.setattr(router, 'installation_token', fail_installation_token)

    result = await router.handle_github_webhook(FakeRequest())

    assert result['ignored'] is True
    assert result['reason'] == 'self-authored-event'


@pytest.mark.asyncio
async def test_installation_repositories_event_posts_opt_in_guidance(
    monkeypatch,
):
    """Repo scope additions must not auto-dispatch active work.

    Regression: previously the install-event branch called
    dispatch_active_work_for_installation, fanning out to every open
    issue and PR in every installed repository. The new design returns
    opt-in guidance text the operator can use to activate specific repos.
    """
    tokens = []
    dispatched = []

    class FakeRequest:
        headers = {
            'X-Hub-Signature-256': 'sha256=test',
            'X-GitHub-Event': 'installation_repositories',
        }

        async def body(self):
            return json.dumps(
                {
                    'action': 'added',
                    'installation': {'id': 123},
                    'repositories_added': [
                        {'full_name': 'owner/one'},
                        {'full_name': 'owner/two'},
                    ],
                }
            ).encode()

    async def fake_verify(signature, body):
        assert signature == 'sha256=test'

    async def fake_installation_token(installation_id):
        tokens.append(installation_id)
        return 'ghs_test', '2026-04-24T22:00:00Z'

    async def fail_dispatch_active_work_for_installation(installation_id):
        dispatched.append(installation_id)
        raise AssertionError(
            'install events must not auto-dispatch active work'
        )

    monkeypatch.setattr(router, 'verify_signature', fake_verify)
    monkeypatch.setattr(router, 'installation_token', fake_installation_token)
    monkeypatch.setattr(
        router,
        'dispatch_active_work_for_installation',
        fail_dispatch_active_work_for_installation,
    )

    result = await router.handle_github_webhook(FakeRequest())

    assert dispatched == []  # regression: no auto-dispatch
    assert tokens == [123]
    assert result['accepted'] is True
    assert result['trigger'] == 'installation_repositories'
    assert result['welcomed_repos'] == ['owner/one', 'owner/two']
    assert 'codetether.active' in result['guidance']


@pytest.mark.asyncio
async def test_self_authored_installation_repositories_event_is_not_backfilled(
    monkeypatch,
):
    app_slug = router.APP_SLUG

    class FakeRequest:
        headers = {
            'X-Hub-Signature-256': 'sha256=test',
            'X-GitHub-Event': 'installation_repositories',
        }

        async def body(self):
            return json.dumps(
                {
                    'action': 'added',
                    'installation': {'id': 123},
                    'sender': {'login': f'{app_slug}[bot]', 'type': 'Bot'},
                }
            ).encode()

    async def fake_verify(signature, body):
        assert signature == 'sha256=test'

    async def fail_dispatch_active_work_for_installation(installation_id):
        raise AssertionError(
            'self-authored events must not trigger active-work backfill'
        )

    async def fail_installation_token(installation_id):
        raise AssertionError(
            'self-authored events should not mint installation tokens'
        )

    monkeypatch.setattr(router, 'verify_signature', fake_verify)
    monkeypatch.setattr(
        router,
        'dispatch_active_work_for_installation',
        fail_dispatch_active_work_for_installation,
    )
    monkeypatch.setattr(router, 'installation_token', fail_installation_token)

    result = await router.handle_github_webhook(FakeRequest())

    assert result == {
        'ignored': True,
        'reason': 'self-authored-event',
        'event': 'installation_repositories',
        'action': 'added',
    }


@pytest.mark.asyncio
async def test_installation_created_event_posts_opt_in_guidance(monkeypatch):
    """First-time installations must not auto-dispatch active work.

    Regression: the install-event branch used to fan out to every open
    issue and PR in every installed repository. The new design returns
    opt-in guidance text only.
    """
    dispatched = []

    class FakeRequest:
        headers = {
            'X-Hub-Signature-256': 'sha256=test',
            'X-GitHub-Event': 'installation',
        }

        async def body(self):
            return json.dumps(
                {
                    'action': 'created',
                    'installation': {'id': 123},
                }
            ).encode()

    async def fake_verify(signature, body):
        assert signature == 'sha256=test'

    async def fake_installation_token(installation_id):
        return 'ghs_test', '2026-04-24T22:00:00Z'

    async def fail_dispatch_active_work_for_installation(installation_id):
        dispatched.append(installation_id)
        raise AssertionError(
            'install events must not auto-dispatch active work'
        )

    monkeypatch.setattr(router, 'verify_signature', fake_verify)
    monkeypatch.setattr(router, 'installation_token', fake_installation_token)
    monkeypatch.setattr(
        router,
        'dispatch_active_work_for_installation',
        fail_dispatch_active_work_for_installation,
    )

    result = await router.handle_github_webhook(FakeRequest())

    assert dispatched == []  # regression: no auto-dispatch
    assert result['accepted'] is True
    assert result['trigger'] == 'installation'
    assert 'codetether.active' in result['guidance']


@pytest.mark.asyncio
async def test_checks_failed_mention_routes_to_fix_handler(monkeypatch):
    calls = []
    app_slug = router.APP_SLUG

    class FakeRequest:
        headers = {
            'X-Hub-Signature-256': 'sha256=test',
            'X-GitHub-Event': 'issue_comment',
        }

        async def body(self):
            return json.dumps(
                {
                    'action': 'created',
                    'installation': {'id': 123},
                    'repository': {'full_name': 'owner/repo'},
                    'issue': {
                        'number': 573,
                        'pull_request': {
                            'url': 'https://api.github.com/repos/owner/repo/pulls/573'
                        },
                    },
                    'comment': {
                        'id': 99,
                        'body': f'@{app_slug}, the checks failed',
                    },
                }
            ).encode()

    async def fake_verify(signature, body):
        assert signature == 'sha256=test'

    async def fake_installation_token(installation_id):
        assert installation_id == 123
        return 'ghs_test', '2026-04-24T22:00:00Z'

    async def fake_has_active_github_app_task(repo, number):
        calls.append(('active-check', repo, number))
        return False

    async def fake_handle_fix_request(context, token):
        calls.append(('fix', context, token))
        return {'accepted': True, 'clone_task_id': 'task-1'}

    async def fail_post_issue_comment(repo, issue_number, token, body):
        raise AssertionError(
            'checks failed mention must not post non-fix guidance'
        )

    monkeypatch.setattr(router, 'verify_signature', fake_verify)
    monkeypatch.setattr(router, 'installation_token', fake_installation_token)
    monkeypatch.setattr(
        router, 'has_active_github_app_task', fake_has_active_github_app_task
    )
    monkeypatch.setattr(router, 'handle_fix_request', fake_handle_fix_request)
    monkeypatch.setattr(router, 'post_issue_comment', fail_post_issue_comment)

    result = await router.handle_github_webhook(FakeRequest())

    assert result == {'accepted': True, 'clone_task_id': 'task-1'}
    fix_calls = [call for call in calls if call[0] == 'fix']
    assert fix_calls
    _, context, token = fix_calls[0]
    assert token == 'ghs_test'
    assert context.repo_full_name == 'owner/repo'
    assert context.issue_number == 573
    assert context.pr_number == 573


@pytest.mark.asyncio
async def test_changes_requested_review_without_mention_creates_fix_task(
    monkeypatch,
):
    calls = []

    class FakeRequest:
        headers = {
            'X-Hub-Signature-256': 'sha256=test',
            'X-GitHub-Event': 'pull_request_review',
        }

        async def body(self):
            return json.dumps(
                {
                    'action': 'submitted',
                    'installation': {'id': 123},
                    'repository': {'full_name': 'owner/repo'},
                    'pull_request': {'number': 7},
                    'review': {
                        'id': 456,
                        'state': 'changes_requested',
                        'body': 'Please add coverage for the new edge case.',
                        'user': {'login': 'reviewer', 'type': 'User'},
                    },
                    'sender': {'login': 'reviewer', 'type': 'User'},
                }
            ).encode()

    async def fake_verify(signature, body):
        assert signature == 'sha256=test'

    async def fake_installation_token(installation_id):
        assert installation_id == 123
        return 'ghs_test', '2026-04-24T22:00:00Z'

    async def fake_has_active_github_app_task(repo, number):
        assert repo == 'owner/repo'
        assert number == 7
        return False

    async def fake_handle_fix_request(context, token):
        calls.append((context, token))
        return {'accepted': True, 'clone_task_id': 'task-review'}

    async def fail_post_issue_comment(repo, issue_number, token, body):
        raise AssertionError(
            'changes-requested reviews should not be treated as non-fix mentions'
        )

    monkeypatch.setattr(router, 'verify_signature', fake_verify)
    monkeypatch.setattr(router, 'installation_token', fake_installation_token)
    monkeypatch.setattr(
        router, 'has_active_github_app_task', fake_has_active_github_app_task
    )
    monkeypatch.setattr(router, 'handle_fix_request', fake_handle_fix_request)
    monkeypatch.setattr(router, 'post_issue_comment', fail_post_issue_comment)

    result = await router.handle_github_webhook(FakeRequest())

    assert result == {'accepted': True, 'clone_task_id': 'task-review'}
    assert len(calls) == 1
    context, token = calls[0]
    assert token == 'ghs_test'
    assert context.repo_full_name == 'owner/repo'
    assert context.issue_number == 7
    assert context.pr_number == 7
    assert context.comment_id == 456
    assert context.comment_body.startswith(
        '@codetether please address the requested PR changes.'
    )
    assert 'Changes requested by reviewer reviewer' in context.comment_body
    assert 'Please add coverage for the new edge case.' in context.comment_body


@pytest.mark.asyncio
async def test_failed_check_event_dedupes_when_active_task_exists(monkeypatch):
    class FakeRequest:
        headers = {
            'X-Hub-Signature-256': 'sha256=test',
            'X-GitHub-Event': 'check_run',
        }

        async def body(self):
            return json.dumps(
                {
                    'action': 'completed',
                    'installation': {'id': 123},
                    'repository': {'full_name': 'owner/repo'},
                    'check_run': {
                        'id': 777,
                        'name': 'CI',
                        'conclusion': 'failure',
                        'app': {
                            'slug': 'github-actions',
                            'name': 'GitHub Actions',
                        },
                        'pull_requests': [{'number': 573}],
                    },
                }
            ).encode()

    async def fake_verify(signature, body):
        assert signature == 'sha256=test'

    async def fake_installation_token(installation_id):
        assert installation_id == 123
        return 'ghs_test', '2026-04-24T22:00:00Z'

    async def fake_has_active_github_app_task(repo, number):
        assert repo == 'owner/repo'
        assert number == 573
        return True

    async def fail_handle_fix_request(context, token):
        raise AssertionError(
            'failed check remediation must dedupe active PR task'
        )

    monkeypatch.setattr(router, 'verify_signature', fake_verify)
    monkeypatch.setattr(router, 'installation_token', fake_installation_token)
    monkeypatch.setattr(
        router, 'has_active_github_app_task', fake_has_active_github_app_task
    )
    monkeypatch.setattr(router, 'handle_fix_request', fail_handle_fix_request)

    result = await router.handle_github_webhook(FakeRequest())

    assert result == {
        'trigger': 'failed_check',
        'accepted': False,
        'reason': 'active-task-exists',
    }


@pytest.mark.asyncio
async def test_non_changes_requested_review_without_mention_is_ignored(
    monkeypatch,
):
    class FakeRequest:
        headers = {
            'X-Hub-Signature-256': 'sha256=test',
            'X-GitHub-Event': 'pull_request_review',
        }

        async def body(self):
            return json.dumps(
                {
                    'action': 'submitted',
                    'installation': {'id': 123},
                    'repository': {'full_name': 'owner/repo'},
                    'pull_request': {'number': 7},
                    'review': {
                        'id': 456,
                        'state': 'commented',
                        'body': 'Looks okay overall.',
                        'user': {'login': 'reviewer', 'type': 'User'},
                    },
                    'sender': {'login': 'reviewer', 'type': 'User'},
                }
            ).encode()

    async def fake_verify(signature, body):
        assert signature == 'sha256=test'

    async def fail_installation_token(installation_id):
        raise AssertionError(
            'installation token should not be minted for unmentioned review comments'
        )

    async def fail_handle_fix_request(context, token):
        raise AssertionError(
            'unmentioned non-changes-requested reviews should not create tasks'
        )

    monkeypatch.setattr(router, 'verify_signature', fake_verify)
    monkeypatch.setattr(router, 'installation_token', fail_installation_token)
    monkeypatch.setattr(router, 'handle_fix_request', fail_handle_fix_request)

    result = await router.handle_github_webhook(FakeRequest())

    assert result['ignored'] is True
    assert result['reason'] == 'no-mention'
    assert result['event'] == 'pull_request_review'
    assert result['action'] == 'submitted'


@pytest.mark.asyncio
async def test_non_fix_guidance_suppressed_when_active_task_exists(monkeypatch):
    app_slug = router.APP_SLUG

    class FakeRequest:
        headers = {
            'X-Hub-Signature-256': 'sha256=test',
            'X-GitHub-Event': 'issue_comment',
        }

        async def body(self):
            return json.dumps(
                {
                    'action': 'created',
                    'installation': {'id': 123},
                    'repository': {'full_name': 'owner/repo'},
                    'issue': {
                        'number': 573,
                        'pull_request': {
                            'url': 'https://api.github.com/repos/owner/repo/pulls/573'
                        },
                    },
                    'comment': {'id': 99, 'body': f'@{app_slug} hello?'},
                }
            ).encode()

    async def fake_verify(signature, body):
        assert signature == 'sha256=test'

    async def fake_installation_token(installation_id):
        assert installation_id == 123
        return 'ghs_test', '2026-04-24T22:00:00Z'

    async def fake_has_active_github_app_task(repo, number):
        assert repo == 'owner/repo'
        assert number == 573
        return True

    async def fail_post_issue_comment(repo, issue_number, token, body):
        raise AssertionError('active PR task should suppress guidance chatter')

    monkeypatch.setattr(router, 'verify_signature', fake_verify)
    monkeypatch.setattr(router, 'installation_token', fake_installation_token)
    monkeypatch.setattr(
        router, 'has_active_github_app_task', fake_has_active_github_app_task
    )
    monkeypatch.setattr(router, 'post_issue_comment', fail_post_issue_comment)

    result = await router.handle_github_webhook(FakeRequest())

    assert result == {'accepted': False, 'reason': 'active-task-exists'}


@pytest.mark.asyncio
async def test_install_event_with_non_dict_installation_payload_is_ignored(
    monkeypatch,
):
    """Defensive: payload['installation'] may be None or non-dict."""
    class FakeRequest:
        headers = {
            'X-Hub-Signature-256': 'sha256=test',
            'X-GitHub-Event': 'installation',
        }

        async def body(self):
            return json.dumps(
                {'action': 'created', 'installation': None}
            ).encode()

    async def fake_verify(signature, body):
        assert signature == 'sha256=test'

    async def fail_installation_token(installation_id):
        raise AssertionError('must not mint token when id is unknown')

    monkeypatch.setattr(router, 'verify_signature', fake_verify)
    monkeypatch.setattr(router, 'installation_token', fail_installation_token)

    result = await router.handle_github_webhook(FakeRequest())

    assert result == {
        'ignored': True,
        'reason': 'missing-installation-id',
        'event': 'installation',
    }


@pytest.mark.asyncio
async def test_install_event_skips_non_dict_repo_entries(monkeypatch):
    """Defensive: repositories_added may contain non-dict entries."""
    class FakeRequest:
        headers = {
            'X-Hub-Signature-256': 'sha256=test',
            'X-GitHub-Event': 'installation_repositories',
        }

        async def body(self):
            return json.dumps(
                {
                    'action': 'added',
                    'installation': {'id': 123},
                    'repositories_added': [
                        'not-a-dict',
                        None,
                        {'full_name': 'owner/valid'},
                        {'full_name': ''},
                    ],
                }
            ).encode()

    async def fake_verify(signature, body):
        assert signature == 'sha256=test'

    async def fake_installation_token(installation_id):
        return 'ghs_test', '2026-04-24T22:00:00Z'

    monkeypatch.setattr(router, 'verify_signature', fake_verify)
    monkeypatch.setattr(router, 'installation_token', fake_installation_token)

    result = await router.handle_github_webhook(FakeRequest())

    assert result['accepted'] is True
    assert result['welcomed_repos'] == ['owner/valid']
