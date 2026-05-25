import os

os.environ.setdefault('DATABASE_URL', 'postgresql://test:test@localhost:5432/test')

import pytest

from a2a_server.github_app import (
    issue_final_comment,
    issue_review_task,
    task_completion,
    task_context,
)


@pytest.fixture
def pr_payload():
    return {
        'number': 77,
        'state': 'open',
        'html_url': 'https://github.com/acme/widgets/pull/77',
        'head': {'sha': 'abc123', 'repo': {'full_name': 'acme/widgets'}},
        'base': {'sha': 'def456'},
    }


def test_issue_pr_provenance_allows_review(pr_payload):
    provenance = issue_review_task.issue_pr_provenance(
        repo='acme/widgets',
        issue_number=12,
        branch='codetether/issue-12',
        pr=pr_payload,
        installation_id=123,
        action='github:review_pr',
        parent_task_id='task-code',
    )

    decision = issue_review_task.policy_decision(provenance, 'github:review_pr')

    assert decision['allowed'] is True
    assert decision['provenance']['complete'] is True
    assert provenance['ap_output']['head_sha'] == 'abc123'
    assert (
        'github:review_pr'
        in provenance['ap_delegation']['chain'][1]['capability']['operations']
    )


def test_issue_pr_provenance_denies_wrong_action(pr_payload):
    provenance = issue_review_task.issue_pr_provenance(
        repo='acme/widgets',
        issue_number=12,
        branch='codetether/issue-12',
        pr=pr_payload,
        installation_id=123,
        action='github:review_pr',
    )

    decision = issue_review_task.policy_decision(provenance, 'github:merge_pr')

    assert decision['allowed'] is False
    assert (
        'action outside delegated capability envelope'
        in decision['provenance']['failures']
    )


@pytest.mark.asyncio
async def test_issue_final_comment_queues_review_task(monkeypatch, pr_payload):
    comments = []
    created = []

    async def fake_context(task):
        return 'acme/widgets', 12, 'codetether/issue-12', 'token'

    async def fake_verify(repo, branch, token):
        return {'branch_exists': True, 'has_commits': True, 'error': None}

    async def fake_open_pr(repo, branch, token):
        return pr_payload

    async def fake_create_review_task(**kwargs):
        created.append(kwargs)
        return 'task-review-1'

    async def fake_post(repo, issue_number, token, body):
        comments.append(body)

    monkeypatch.setattr(issue_final_comment, 'issue_task_context', fake_context)
    monkeypatch.setattr(
        issue_final_comment, '_verify_branch_and_commits', fake_verify
    )
    monkeypatch.setattr(issue_final_comment, 'open_issue_pr', fake_open_pr)
    monkeypatch.setattr(issue_final_comment, 'post_issue_comment', fake_post)
    monkeypatch.setattr(
        issue_review_task, 'create_issue_review_task', fake_create_review_task
    )

    await issue_final_comment.notify_issue_final_comment(
        {
            'id': 'task-code',
            'status': 'completed',
            'result': 'done',
            'metadata': {
                'workspace_id': 'ws1',
                'github_issue_url': 'https://github.com/acme/widgets/issues/12',
                'github_installation_id': 123,
                'target_worker_id': 'wrk1',
            },
        }
    )

    assert created
    assert created[0]['parent_task_id'] == 'task-code'
    assert created[0]['pr']['number'] == 77
    assert 'target_worker_id' not in created[0]
    assert 'Queued CodeTether reviewer task `task-review-1`' in comments[0]
    assert 'Automation provenance:' in comments[0]


@pytest.mark.asyncio
async def test_review_completion_queues_merge_task(monkeypatch):
    calls = []

    async def fake_context(task):
        return 'acme/widgets', 77, 'codetether/issue-12', 'token'

    async def fake_create_merge_task(review_task, token):
        calls.append((review_task, token))
        return 'task-merge-1'

    monkeypatch.setattr(task_context, 'github_app_task_context', fake_context)
    monkeypatch.setattr(
        issue_review_task, 'create_issue_merge_task', fake_create_merge_task
    )

    task = {
        'id': 'task-review-1',
        'title': 'Review issue PR #77',
        'status': 'completed',
        'metadata': {'source': 'github-app', 'workflow_stage': 'review'},
    }

    await task_completion.notify_issue_task_completion(task)

    assert calls == [(task, 'token')]


@pytest.mark.asyncio
async def test_create_review_task_records_allow_decision_without_builder_target(
    monkeypatch, pr_payload
):
    created = []
    decisions = []

    async def fake_dispatch(**kwargs):
        created.append(kwargs)
        return 'task-review-1'

    async def fake_record(**kwargs):
        decisions.append(kwargs)

    monkeypatch.setattr(
        'a2a_server.persistent_worker_pool.create_and_dispatch_task',
        fake_dispatch,
    )
    monkeypatch.setattr(
        issue_review_task, 'record_automation_decision', fake_record
    )

    task_id = await issue_review_task.create_issue_review_task(
        workspace_id='ws1',
        repo='acme/widgets',
        issue_number=12,
        branch='codetether/issue-12',
        pr=pr_payload,
        github_issue_url='https://github.com/acme/widgets/issues/12',
        github_installation_id=123,
        parent_task_id='task-code',
        target_worker_id='builder-worker',
    )

    assert task_id == 'task-review-1'
    assert created[0]['metadata']['worker_personality'] == 'reviewer'
    assert 'target_worker_id' not in created[0]['metadata']
    assert 'without mentioning the CodeTether bot' in created[0]['prompt']
    assert 'Source issue / Definition of Done' in created[0]['prompt']
    assert 'Issue DoD' in created[0]['prompt']
    assert (
        'Never approve if the issue DoD checklist has any missing or unproven item'
        in created[0]['prompt']
    )
    assert 'If anything requires changes' in created[0]['prompt']
    assert decisions[0]['decision']['allowed'] is True
    assert decisions[0]['task_id'] == 'task-review-1'


@pytest.mark.asyncio
async def test_create_review_task_records_deny_decision(
    monkeypatch, pr_payload
):
    decisions = []

    def fake_policy(provenance, action):
        return {
            'allowed': False,
            'action': action,
            'provenance': {'failures': ['denied']},
        }

    async def fake_record(**kwargs):
        decisions.append(kwargs)

    monkeypatch.setattr(issue_review_task, 'policy_decision', fake_policy)
    monkeypatch.setattr(
        issue_review_task, 'record_automation_decision', fake_record
    )

    task_id = await issue_review_task.create_issue_review_task(
        workspace_id='ws1',
        repo='acme/widgets',
        issue_number=12,
        branch='codetether/issue-12',
        pr=pr_payload,
        github_issue_url='https://github.com/acme/widgets/issues/12',
        github_installation_id=123,
        parent_task_id='task-code',
    )

    assert task_id is None
    assert decisions[0]['decision']['allowed'] is False
    assert decisions[0]['task_id'] == 'task-code'


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'review_result',
    [
        'CHANGES_REQUESTED: tests failed',
        'BLOCKED: provenance mismatch',
        'completed without verdict',
    ],
)
async def test_create_merge_task_requires_explicit_approval(
    monkeypatch, review_result
):
    called = False
    comments = []

    async def fake_github_json(*args, **kwargs):
        nonlocal called
        called = True
        return {}

    async def fake_post(repo, issue_number, token, body):
        comments.append(body)

    async def fake_fix_followup(*, review_task, token):
        return None  # simulate fix follow-up unable to create task

    monkeypatch.setattr(
        'a2a_server.github_app.auth.github_json', fake_github_json
    )
    monkeypatch.setattr(
        'a2a_server.github_app.watch.post_issue_comment', fake_post
    )
    monkeypatch.setattr(
        issue_review_task, 'create_fix_followup_task', fake_fix_followup
    )

    task_id = await issue_review_task.create_issue_merge_task(
        review_task={
            'id': 'task-review-1',
            'result': review_result,
            'metadata': {
                'workspace_id': 'ws1',
                'repo': 'acme/widgets',
                'issue_number': 12,
                'pr_number': 77,
                'branch_name': 'codetether/issue-12',
            },
        },
        token='token',
    )

    assert task_id is None
    if review_result.startswith(('CHANGES_REQUESTED', 'BLOCKED')):
        assert (
            '@codetether please address the requested PR changes' in comments[0]
        )
    else:
        assert comments == []


@pytest.mark.asyncio
async def test_change_request_followup_skips_duplicate_tag(monkeypatch):
    comments = []

    async def fake_post(repo, issue_number, token, body):
        comments.append(body)

    async def fake_fix_followup(*, review_task, token):
        # The fix follow-up runs first; simulate it succeeding so the
        # @codetether fallback is never reached. This test verifies that
        # when the fix follow-up succeeds, no duplicate @codetether comment
        # is posted.
        return 'task-fix-dup'

    monkeypatch.setattr(
        'a2a_server.github_app.watch.post_issue_comment', fake_post
    )
    monkeypatch.setattr(
        issue_review_task, 'create_fix_followup_task', fake_fix_followup
    )

    task_id = await issue_review_task.create_issue_merge_task(
        review_task={
            'id': 'task-review-1',
            'result': 'CHANGES_REQUESTED: @codetether please address tests',
            'metadata': {
                'workspace_id': 'ws1',
                'repo': 'acme/widgets',
                'issue_number': 12,
                'pr_number': 77,
                'branch_name': 'codetether/issue-12',
            },
        },
        token='token',
    )

    assert task_id is None
    # No @codetether fallback comment was posted (fix follow-up handled it)
    assert all('@codetether please address' not in c for c in comments)


def test_reviewer_approval_ignores_blocked_prose():
    assert (
        issue_review_task.reviewer_allows_merge(
            {
                'result': (
                    'Self-approval is blocked by GitHub, so I left an approving comment instead.\n'
                    '## Final Verdict: **APPROVED**\n\n'
                    'Validation passed.'
                )
            }
        )
        is True
    )


@pytest.mark.asyncio
async def test_create_merge_task_records_sha_mismatch(monkeypatch, pr_payload):
    decisions = []
    comments = []

    async def fake_github_json(method, path, token):
        updated = dict(pr_payload)
        updated['head'] = {'sha': 'newsha'}
        return updated

    async def fake_record(**kwargs):
        decisions.append(kwargs)

    async def fake_post(repo, issue_number, token, body):
        comments.append((repo, issue_number, body))

    monkeypatch.setattr(
        'a2a_server.github_app.auth.github_json', fake_github_json
    )
    monkeypatch.setattr(
        issue_review_task, 'record_automation_decision', fake_record
    )
    monkeypatch.setattr(
        'a2a_server.github_app.watch.post_issue_comment', fake_post
    )

    task_id = await issue_review_task.create_issue_merge_task(
        review_task={
            'id': 'task-review-1',
            'result': 'APPROVED: looks safe',
            'metadata': {
                'workspace_id': 'ws1',
                'repo': 'acme/widgets',
                'issue_number': 12,
                'pr_number': 77,
                'branch_name': 'codetether/issue-12',
                'pr_head_sha': 'abc123',
                'github_installation_id': 123,
            },
        },
        token='token',
    )

    assert task_id is None
    assert decisions[0]['decision']['allowed'] is False
    assert (
        'PR head SHA changed'
        in decisions[0]['decision']['provenance']['failures'][0]
    )
    assert 'Blocked because the PR changed' in comments[0][2]


@pytest.mark.asyncio
async def test_create_merge_task_blocks_unresolved_review_feedback(
    monkeypatch, pr_payload
):
    decisions = []
    comments = []

    async def fake_github_json(method, path, token):
        if path == '/repos/acme/widgets/pulls/77':
            return pr_payload
        raise AssertionError(f'unexpected GitHub call: {method} {path}')

    async def fake_feedback_status(repo, pr_number, token):
        return {
            'feedback_addressed': False,
            'blockers': [
                'Unresolved review thread at src/app.py:10 by reviewer'
            ],
        }

    async def fake_record(**kwargs):
        decisions.append(kwargs)

    async def fake_post(repo, issue_number, token, body):
        comments.append(body)

    monkeypatch.setattr(
        'a2a_server.github_app.auth.github_json', fake_github_json
    )
    monkeypatch.setattr(
        issue_review_task, 'review_feedback_status', fake_feedback_status
    )
    monkeypatch.setattr(
        issue_review_task, 'record_automation_decision', fake_record
    )
    monkeypatch.setattr(
        'a2a_server.github_app.watch.post_issue_comment', fake_post
    )

    task_id = await issue_review_task.create_issue_merge_task(
        review_task={
            'id': 'task-review-1',
            'result': 'APPROVED: looks safe',
            'metadata': {
                'workspace_id': 'ws1',
                'repo': 'acme/widgets',
                'issue_number': 12,
                'pr_number': 77,
                'branch_name': 'codetether/issue-12',
                'pr_head_sha': 'abc123',
                'github_installation_id': 123,
            },
        },
        token='token',
    )

    assert task_id is None
    assert decisions[0]['decision']['allowed'] is False
    assert (
        'Unresolved review thread'
        in decisions[0]['decision']['provenance']['failures'][0]
    )
    assert 'review feedback is not fully addressed' in comments[0]


@pytest.mark.asyncio
async def test_create_merge_task_auto_merges_when_feedback_addressed(
    monkeypatch, pr_payload
):
    decisions = []
    comments = []
    calls = []

    async def fake_github_json(method, path, token, payload=None):
        calls.append((method, path, payload))
        if path == '/repos/acme/widgets/pulls/77':
            return pr_payload
        if path == '/repos/acme/widgets':
            return {
                'allow_squash_merge': True,
                'allow_rebase_merge': True,
                'allow_merge_commit': True,
            }
        if method == 'PUT' and path == '/repos/acme/widgets/pulls/77/merge':
            assert payload['sha'] == 'abc123'
            assert payload['merge_method'] == 'squash'
            return {'merged': True, 'sha': 'merge123'}
        raise AssertionError(f'unexpected GitHub call: {method} {path}')

    async def fake_feedback_status(repo, pr_number, token):
        return {'feedback_addressed': True, 'blockers': []}

    async def fake_status_check_status(repo, sha, token):
        return {'checks_green': True, 'blockers': []}

    async def fake_record(**kwargs):
        decisions.append(kwargs)

    async def fake_post(repo, issue_number, token, body):
        comments.append(body)

    monkeypatch.setattr(
        'a2a_server.github_app.auth.github_json', fake_github_json
    )
    monkeypatch.setattr(
        issue_review_task, 'review_feedback_status', fake_feedback_status
    )
    monkeypatch.setattr(
        issue_review_task, 'status_check_status', fake_status_check_status
    )
    monkeypatch.setattr(
        issue_review_task, 'record_automation_decision', fake_record
    )
    monkeypatch.setattr(
        'a2a_server.github_app.watch.post_issue_comment', fake_post
    )
    monkeypatch.setattr(issue_review_task, 'AUTO_MERGE_ENABLED', True)

    result = await issue_review_task.create_issue_merge_task(
        review_task={
            'id': 'task-review-1',
            'result': 'APPROVED: looks safe',
            'metadata': {
                'workspace_id': 'ws1',
                'repo': 'acme/widgets',
                'issue_number': 12,
                'pr_number': 77,
                'branch_name': 'codetether/issue-12',
                'pr_head_sha': 'abc123',
                'github_installation_id': 123,
            },
        },
        token='token',
    )

    assert result == 'merge123'
    assert any(
        call[1] == '/repos/acme/widgets/pulls/77/merge' for call in calls
    )
    assert decisions[-1]['decision']['allowed'] is True
    assert 'Merged PR #77 using `squash`' in comments[0]


@pytest.mark.asyncio
async def test_create_merge_task_enables_github_auto_merge_when_direct_merge_blocked(
    monkeypatch, pr_payload
):
    decisions = []
    comments = []
    graphql_calls = []
    pr_with_node = dict(pr_payload)
    pr_with_node['node_id'] = 'PR_kwDOAutoMerge'

    async def fake_github_json(method, path, token, payload=None):
        if path == '/repos/acme/widgets/pulls/77':
            return pr_with_node
        if path == '/repos/acme/widgets':
            return {
                'allow_squash_merge': True,
                'allow_rebase_merge': True,
                'allow_merge_commit': True,
            }
        if method == 'PUT' and path == '/repos/acme/widgets/pulls/77/merge':
            raise RuntimeError(
                'Repository rule violations found: Cannot update this protected ref.'
            )
        raise AssertionError(f'unexpected GitHub call: {method} {path}')

    async def fake_github_graphql(query, variables, token):
        graphql_calls.append(variables)
        return {
            'enablePullRequestAutoMerge': {
                'pullRequest': {
                    'number': 77,
                    'autoMergeRequest': {
                        'enabledAt': '2026-05-08T15:50:00Z',
                        'mergeMethod': 'SQUASH',
                    },
                },
            },
        }

    async def fake_feedback_status(repo, pr_number, token):
        return {'feedback_addressed': True, 'blockers': []}

    async def fake_status_check_status(repo, sha, token):
        return {'checks_green': True, 'blockers': []}

    async def fake_record(**kwargs):
        decisions.append(kwargs)

    async def fake_post(repo, issue_number, token, body):
        comments.append(body)

    monkeypatch.setattr(
        'a2a_server.github_app.auth.github_json', fake_github_json
    )
    monkeypatch.setattr(
        'a2a_server.github_app.auth.github_graphql', fake_github_graphql
    )
    monkeypatch.setattr(
        issue_review_task, 'review_feedback_status', fake_feedback_status
    )
    monkeypatch.setattr(
        issue_review_task, 'status_check_status', fake_status_check_status
    )
    monkeypatch.setattr(
        issue_review_task, 'record_automation_decision', fake_record
    )
    monkeypatch.setattr(
        'a2a_server.github_app.watch.post_issue_comment', fake_post
    )
    monkeypatch.setattr(issue_review_task, 'AUTO_MERGE_ENABLED', True)

    result = await issue_review_task.create_issue_merge_task(
        review_task={
            'id': 'task-review-1',
            'result': '## Final Verdict: **APPROVED**',
            'metadata': {
                'workspace_id': 'ws1',
                'repo': 'acme/widgets',
                'issue_number': 12,
                'pr_number': 77,
                'branch_name': 'codetether/issue-12',
                'pr_head_sha': 'abc123',
                'github_installation_id': 123,
            },
        },
        token='token',
    )

    assert result == 'auto_merge_enabled'
    assert graphql_calls[0]['pullRequestId'] == 'PR_kwDOAutoMerge'
    assert graphql_calls[0]['mergeMethod'] == 'SQUASH'
    assert graphql_calls[0]['expectedHeadOid'] == 'abc123'
    assert decisions[-1]['decision']['allowed'] is True
    assert 'Enabled GitHub auto-merge for PR #77 using `squash`' in comments[0]


@pytest.mark.asyncio
async def test_create_merge_task_blocks_failed_status_checks(
    monkeypatch, pr_payload
):
    decisions = []
    comments = []
    calls = []

    async def fake_github_json(method, path, token, payload=None):
        calls.append((method, path, payload))
        if path == '/repos/acme/widgets/pulls/77':
            return pr_payload
        raise AssertionError(f'unexpected GitHub call: {method} {path}')

    async def fake_feedback_status(repo, pr_number, token):
        return {'feedback_addressed': True, 'blockers': []}

    async def fake_status_check_status(repo, sha, token):
        return {
            'checks_green': False,
            'blockers': ['Check `Lint Code Base` concluded failure'],
        }

    async def fake_record(**kwargs):
        decisions.append(kwargs)

    async def fake_post(repo, issue_number, token, body):
        comments.append(body)

    monkeypatch.setattr(
        'a2a_server.github_app.auth.github_json', fake_github_json
    )
    monkeypatch.setattr(
        issue_review_task, 'review_feedback_status', fake_feedback_status
    )
    monkeypatch.setattr(
        issue_review_task, 'status_check_status', fake_status_check_status
    )
    monkeypatch.setattr(
        issue_review_task, 'record_automation_decision', fake_record
    )
    monkeypatch.setattr(
        'a2a_server.github_app.watch.post_issue_comment', fake_post
    )
    monkeypatch.setattr(issue_review_task, 'AUTO_MERGE_ENABLED', True)

    result = await issue_review_task.create_issue_merge_task(
        review_task={
            'id': 'task-review-1',
            'result': 'APPROVED: looks safe',
            'metadata': {
                'workspace_id': 'ws1',
                'repo': 'acme/widgets',
                'issue_number': 12,
                'pr_number': 77,
                'branch_name': 'codetether/issue-12',
                'pr_head_sha': 'abc123',
                'github_installation_id': 123,
            },
        },
        token='token',
    )

    assert result is None
    assert all('/merge' not in call[1] for call in calls)
    assert decisions[-1]['decision']['allowed'] is False
    assert 'PR status checks are not green' in comments[0]
    assert 'Lint Code Base' in comments[0]


def test_merge_provenance_uses_merge_steward_actor(pr_payload):
    provenance = issue_review_task.issue_pr_provenance(
        repo='acme/widgets',
        issue_number=12,
        branch='codetether/issue-12',
        pr=pr_payload,
        installation_id=123,
        action='github:merge_pr',
    )

    assert (
        provenance['ap_delegation']['chain'][1]['actor']
        == 'codetether-merge-steward'
    )


# ---------------------------------------------------------------------------
# Protocol-native fix follow-up tests (issue #71)
# ---------------------------------------------------------------------------


def _make_review_task(
    verdict_text, *, pr_head_sha='abc123', extra_metadata=None
):
    """Build a review task dict with the given verdict in the result field."""
    metadata = {
        'workspace_id': 'ws1',
        'repo': 'acme/widgets',
        'issue_number': 12,
        'pr_number': 77,
        'branch_name': 'codetether/issue-12',
        'pr_head_sha': pr_head_sha,
        'github_installation_id': 123,
        'github_issue_url': 'https://github.com/acme/widgets/pull/77',
    }
    if extra_metadata:
        metadata.update(extra_metadata)
    return {
        'id': 'task-review-1',
        'status': 'completed',
        'result': verdict_text,
        'metadata': metadata,
    }


@pytest.mark.asyncio
async def test_fix_followup_creates_task_on_changes_requested(
    monkeypatch, pr_payload
):
    """CHANGES_REQUESTED verdict enqueues a protocol-native fix task."""
    dispatched = []
    comments = []

    async def fake_github_json(method, path, token):
        return pr_payload

    async def fake_dispatch(**kwargs):
        dispatched.append(kwargs)
        return 'task-fix-1'

    async def fake_record(**kwargs):
        pass

    async def fake_post(repo, issue_number, token, body):
        comments.append(body)

    async def fake_count(*args, **kwargs):
        return 0

    monkeypatch.setattr(
        'a2a_server.github_app.auth.github_json', fake_github_json
    )
    monkeypatch.setattr(
        'a2a_server.persistent_worker_pool.create_and_dispatch_task',
        fake_dispatch,
    )
    monkeypatch.setattr(
        issue_review_task, 'record_automation_decision', fake_record
    )
    monkeypatch.setattr(
        'a2a_server.github_app.watch.post_issue_comment', fake_post
    )
    monkeypatch.setattr(issue_review_task, '_count_fix_attempts', fake_count)

    task_id = await issue_review_task.create_fix_followup_task(
        review_task=_make_review_task('CHANGES_REQUESTED: tests failed'),
        token='token',
    )

    assert task_id == 'task-fix-1'
    assert len(dispatched) == 1
    meta = dispatched[0]['metadata']
    assert meta['fix_followup'] == 'true'
    assert meta['review_task_id'] == 'task-review-1'
    assert meta['review_verdict'] == 'CHANGES_REQUESTED'
    assert meta['workflow_stage'] == 'fix'
    assert meta['pr_head_sha'] == 'abc123'
    assert 'Reviewer verdict: `CHANGES_REQUESTED`' in comments[0]
    assert 'Protocol-native fix task `task-fix-1`' in comments[0]
    assert '@codetether' not in comments[0]


def test_change_request_action_line_tags_only_mention_path():
    protocol_line = issue_review_task.change_request_action_line(
        'CHANGES_REQUESTED', task_id='task-fix-1'
    )
    mention_line = issue_review_task.change_request_action_line(
        'CHANGES_REQUESTED'
    )

    assert protocol_line.startswith('Protocol-native fix task')
    assert '@codetether' not in protocol_line
    assert mention_line.startswith('@codetether please address')
    assert '`CHANGES_REQUESTED`' in protocol_line


@pytest.mark.asyncio
async def test_fix_followup_creates_task_on_blocked(monkeypatch, pr_payload):
    """BLOCKED verdict enqueues a protocol-native fix task."""
    dispatched = []

    async def fake_github_json(method, path, token):
        return pr_payload

    async def fake_dispatch(**kwargs):
        dispatched.append(kwargs)
        return 'task-fix-2'

    async def fake_record(**kwargs):
        pass

    async def fake_post(*args, **kwargs):
        pass

    async def fake_count(*args, **kwargs):
        return 0

    monkeypatch.setattr(
        'a2a_server.github_app.auth.github_json', fake_github_json
    )
    monkeypatch.setattr(
        'a2a_server.persistent_worker_pool.create_and_dispatch_task',
        fake_dispatch,
    )
    monkeypatch.setattr(
        issue_review_task, 'record_automation_decision', fake_record
    )
    monkeypatch.setattr(
        'a2a_server.github_app.watch.post_issue_comment', fake_post
    )
    monkeypatch.setattr(issue_review_task, '_count_fix_attempts', fake_count)

    task_id = await issue_review_task.create_fix_followup_task(
        review_task=_make_review_task('BLOCKED: provenance mismatch'),
        token='token',
    )

    assert task_id == 'task-fix-2'
    assert dispatched[0]['metadata']['review_verdict'] == 'BLOCKED'


@pytest.mark.asyncio
async def test_fix_followup_skips_approved(monkeypatch):
    """APPROVED verdict does not create a fix task."""
    task_id = await issue_review_task.create_fix_followup_task(
        review_task=_make_review_task('APPROVED: looks good'),
        token='token',
    )
    assert task_id is None


@pytest.mark.asyncio
async def test_fix_followup_skips_no_verdict(monkeypatch):
    """A review with no parseable verdict does not create a fix task."""
    task_id = await issue_review_task.create_fix_followup_task(
        review_task=_make_review_task('inconclusive review text'),
        token='token',
    )
    assert task_id is None


@pytest.mark.asyncio
async def test_fix_followup_skips_closed_pr(monkeypatch):
    """Fix follow-up is not created when the PR is closed."""
    closed_pr = {
        'number': 77,
        'state': 'closed',
        'html_url': 'https://github.com/acme/widgets/pull/77',
        'head': {'sha': 'abc123', 'ref': 'codetether/issue-12'},
        'base': {'sha': 'def456'},
    }

    async def fake_github_json(method, path, token):
        return closed_pr

    monkeypatch.setattr(
        'a2a_server.github_app.auth.github_json', fake_github_json
    )

    task_id = await issue_review_task.create_fix_followup_task(
        review_task=_make_review_task('CHANGES_REQUESTED: tests failed'),
        token='token',
    )
    assert task_id is None


@pytest.mark.asyncio
async def test_fix_followup_skips_sha_mismatch(monkeypatch, pr_payload):
    """Fix follow-up is not created when the PR head SHA changed since review."""
    changed_pr = dict(pr_payload)
    changed_pr['head'] = {'sha': 'newsha999', 'ref': 'codetether/issue-12'}

    async def fake_github_json(method, path, token):
        return changed_pr

    monkeypatch.setattr(
        'a2a_server.github_app.auth.github_json', fake_github_json
    )

    task_id = await issue_review_task.create_fix_followup_task(
        review_task=_make_review_task('CHANGES_REQUESTED: tests failed'),
        token='token',
    )
    assert task_id is None


@pytest.mark.asyncio
async def test_fix_followup_skips_forked_pr(monkeypatch):
    """Fix follow-up is not created when the PR is from a fork."""
    forked_pr = {
        'number': 77,
        'state': 'open',
        'html_url': 'https://github.com/acme/widgets/pull/77',
        'head': {
            'sha': 'abc123',
            'ref': 'codetether/issue-12',
            'repo': {
                'full_name': 'other-user/widgets',
                'clone_url': 'https://github.com/other-user/widgets.git',
            },
        },
        'base': {'sha': 'def456'},
    }

    async def fake_github_json(method, path, token):
        return forked_pr

    monkeypatch.setattr(
        'a2a_server.github_app.auth.github_json', fake_github_json
    )

    task_id = await issue_review_task.create_fix_followup_task(
        review_task=_make_review_task('CHANGES_REQUESTED: tests failed'),
        token='token',
    )
    assert task_id is None


@pytest.mark.asyncio
async def test_fix_followup_skips_missing_metadata(monkeypatch):
    """Fix follow-up is not created when required metadata is missing."""
    task = {
        'id': 'task-review-1',
        'status': 'completed',
        'result': 'CHANGES_REQUESTED: fix tests',
        'metadata': {
            'source': 'github-app',
            'repo': 'acme/widgets',
        },  # missing most fields
    }

    task_id = await issue_review_task.create_fix_followup_task(
        review_task=task,
        token='token',
    )
    assert task_id is None


@pytest.mark.asyncio
async def test_fix_followup_enforces_max_attempts(monkeypatch, pr_payload):
    """Fix follow-up is not created after MAX_FIX_ATTEMPTS_PER_SHA attempts."""
    comments = []

    async def fake_github_json(method, path, token):
        return pr_payload

    async def fake_count(repo, pr_number, head_sha):
        return issue_review_task.MAX_FIX_ATTEMPTS_PER_SHA  # already at max

    async def fake_post(repo, issue_number, token, body):
        comments.append(body)

    monkeypatch.setattr(
        'a2a_server.github_app.auth.github_json', fake_github_json
    )
    monkeypatch.setattr(issue_review_task, '_count_fix_attempts', fake_count)
    monkeypatch.setattr(
        'a2a_server.github_app.watch.post_issue_comment', fake_post
    )

    task_id = await issue_review_task.create_fix_followup_task(
        review_task=_make_review_task('CHANGES_REQUESTED: tests failed'),
        token='token',
    )

    assert task_id is None
    assert 'Maximum fix attempts' in comments[0]


@pytest.mark.asyncio
async def test_fix_followup_includes_review_context_in_prompt(
    monkeypatch, pr_payload
):
    """The fix prompt includes review summary, changed files, blockers, and provenance."""
    dispatched = []

    async def fake_github_json(method, path, token):
        return pr_payload

    async def fake_dispatch(**kwargs):
        dispatched.append(kwargs)
        return 'task-fix-ctx'

    async def fake_record(**kwargs):
        pass

    async def fake_post(*args, **kwargs):
        pass

    async def fake_count(*args, **kwargs):
        return 0

    monkeypatch.setattr(
        'a2a_server.github_app.auth.github_json', fake_github_json
    )
    monkeypatch.setattr(
        'a2a_server.persistent_worker_pool.create_and_dispatch_task',
        fake_dispatch,
    )
    monkeypatch.setattr(
        issue_review_task, 'record_automation_decision', fake_record
    )
    monkeypatch.setattr(
        'a2a_server.github_app.watch.post_issue_comment', fake_post
    )
    monkeypatch.setattr(issue_review_task, '_count_fix_attempts', fake_count)

    task_id = await issue_review_task.create_fix_followup_task(
        review_task=_make_review_task(
            'CHANGES_REQUESTED: tests failed for src/app.py',
            extra_metadata={
                'changed_files': ['src/app.py', 'tests/test_app.py'],
                'blockers': ['Test test_foo fails with assertion error'],
                'last_validation_errors': 'FAILED test_foo - AssertionError',
            },
        ),
        token='token',
    )

    assert task_id == 'task-fix-ctx'
    prompt = dispatched[0]['prompt']
    assert 'src/app.py' in prompt
    assert 'Test test_foo fails' in prompt
    assert 'FAILED test_foo' in prompt
    assert 'CHANGES_REQUESTED' in prompt


@pytest.mark.asyncio
async def test_create_merge_task_uses_protocol_native_fix_as_primary(
    monkeypatch, pr_payload
):
    """create_issue_merge_task calls create_fix_followup_task as primary path."""
    fix_created = []
    fallback_called = []

    async def fake_fix_followup(*, review_task, token):
        fix_created.append((review_task, token))
        return 'task-fix-primary'

    async def fake_fallback(*, review_task, token):
        fallback_called.append(True)
        return False

    monkeypatch.setattr(
        issue_review_task, 'create_fix_followup_task', fake_fix_followup
    )
    monkeypatch.setattr(
        issue_review_task,
        'post_change_request_followup_if_needed',
        fake_fallback,
    )

    task_id = await issue_review_task.create_issue_merge_task(
        review_task=_make_review_task('CHANGES_REQUESTED: tests failed'),
        token='token',
    )

    assert task_id is None
    assert len(fix_created) == 1
    assert len(fallback_called) == 0  # fallback NOT called when fix succeeds


@pytest.mark.asyncio
async def test_create_merge_task_falls_back_to_mention_on_fix_failure(
    monkeypatch, pr_payload
):
    """create_issue_merge_task falls back to @codetether mention when fix follow-up returns None."""
    fix_created = []
    fallback_called = []

    async def fake_fix_followup(*, review_task, token):
        fix_created.append(True)
        return None  # fix follow-up could not create task

    async def fake_fallback(*, review_task, token):
        fallback_called.append(True)
        return False

    monkeypatch.setattr(
        issue_review_task, 'create_fix_followup_task', fake_fix_followup
    )
    monkeypatch.setattr(
        issue_review_task,
        'post_change_request_followup_if_needed',
        fake_fallback,
    )

    task_id = await issue_review_task.create_issue_merge_task(
        review_task=_make_review_task('CHANGES_REQUESTED: tests failed'),
        token='token',
    )

    assert task_id is None
    assert len(fix_created) == 1
    assert len(fallback_called) == 1  # fallback IS called when fix returns None


@pytest.mark.asyncio
async def test_create_merge_task_does_not_call_fix_on_approval(
    monkeypatch, pr_payload
):
    """create_issue_merge_task does not call fix follow-up for APPROVED reviews."""
    fix_created = []

    async def fake_fix_followup(*, review_task, token):
        fix_created.append(True)
        return None

    async def fake_github_json(method, path, token, payload=None):
        if path == '/repos/acme/widgets/pulls/77':
            return pr_payload
        if path == '/repos/acme/widgets':
            return {
                'allow_squash_merge': True,
                'allow_rebase_merge': True,
                'allow_merge_commit': True,
            }
        if method == 'PUT' and 'merge' in path:
            return {'merged': True, 'sha': 'merge123'}
        raise AssertionError(f'unexpected call: {method} {path}')

    async def fake_feedback_status(repo, pr_number, token):
        return {'feedback_addressed': True, 'blockers': []}

    async def fake_status_check_status(repo, sha, token):
        return {'checks_green': True, 'blockers': []}

    async def fake_record(**kwargs):
        pass

    async def fake_post(*args, **kwargs):
        pass

    monkeypatch.setattr(
        issue_review_task, 'create_fix_followup_task', fake_fix_followup
    )
    monkeypatch.setattr(
        'a2a_server.github_app.auth.github_json', fake_github_json
    )
    monkeypatch.setattr(
        issue_review_task, 'review_feedback_status', fake_feedback_status
    )
    monkeypatch.setattr(
        issue_review_task, 'status_check_status', fake_status_check_status
    )
    monkeypatch.setattr(
        issue_review_task, 'record_automation_decision', fake_record
    )
    monkeypatch.setattr(
        'a2a_server.github_app.watch.post_issue_comment', fake_post
    )

    # Use AUTO_MERGE_ENABLED path
    monkeypatch.setattr(issue_review_task, 'AUTO_MERGE_ENABLED', True)

    await issue_review_task.create_issue_merge_task(
        review_task=_make_review_task('APPROVED: looks safe'),
        token='token',
    )

    # No fix task should have been created for an approved review
    assert len(fix_created) == 0


def test_fix_followup_prompt_includes_attempt_counter():
    """The fix prompt includes attempt counter for retry attempts."""
    prompt = issue_review_task.fix_followup_prompt(
        repo='acme/widgets',
        issue_number=12,
        pr_number=77,
        branch='codetether/issue-12',
        head_sha='abc123',
        pr_url='https://github.com/acme/widgets/pull/77',
        verdict='CHANGES_REQUESTED',
        review_summary='Tests failed',
        attempt=3,
    )
    assert 'Fix attempt 3 of 5' in prompt


def test_fix_followup_prompt_no_attempt_on_first():
    """The fix prompt omits attempt counter on first attempt."""
    prompt = issue_review_task.fix_followup_prompt(
        repo='acme/widgets',
        issue_number=12,
        pr_number=77,
        branch='codetether/issue-12',
        head_sha='abc123',
        pr_url='https://github.com/acme/widgets/pull/77',
        verdict='CHANGES_REQUESTED',
        review_summary='Tests failed',
        attempt=1,
    )
    assert 'Fix attempt' not in prompt

@pytest.mark.asyncio
async def test_branch_verification_uses_git_ref_endpoint(monkeypatch):
    calls = []

    async def fake_github_json(method, path, token):
        calls.append((method, path, token))
        return {'object': {'type': 'commit', 'sha': 'abc123'}}

    monkeypatch.setattr(
        'a2a_server.github_app.auth.github_json', fake_github_json
    )

    result = await issue_final_comment._verify_branch_and_commits(
        'CodeTether/TetherScript', 'codetether/issue-12', 'token'
    )

    assert result == {
        'branch_exists': True,
        'has_commits': True,
        'head_sha': 'abc123',
        'error': None,
    }
    assert calls == [
        (
            'GET',
            '/repos/CodeTether/TetherScript/git/ref/heads/codetether%2Fissue-12',
            'token',
        )
    ]


@pytest.mark.asyncio
async def test_issue_final_comment_reports_missing_branch_as_infra_failure(monkeypatch):
    comments = []

    async def fake_context(task):
        return 'CodeTether/TetherScript', 12, 'codetether/issue-12', 'token'

    async def fake_verify(repo, branch, token):
        return {
            'branch_exists': False,
            'has_commits': False,
            'head_sha': '',
            'error': '404 ref not found',
        }

    async def fake_post(repo, issue_number, token, body):
        comments.append(body)

    monkeypatch.setattr(issue_final_comment, 'issue_task_context', fake_context)
    monkeypatch.setattr(
        issue_final_comment, '_verify_branch_and_commits', fake_verify
    )
    monkeypatch.setattr(issue_final_comment, 'post_issue_comment', fake_post)

    await issue_final_comment.notify_issue_final_comment(
        {
            'id': 'task-code',
            'status': 'completed',
            'result': 'worker said done',
            'metadata': {'source': 'github-app'},
        }
    )

    assert len(comments) == 1
    assert 'Branch verification failed after worker completion' in comments[0]
    assert 'GET /repos/CodeTether/TetherScript/git/ref/heads/codetether%2Fissue-12' in comments[0]
    assert 'Recovery: retry or investigate worker commit/push/auth' in comments[0]
    assert 'did not push commits' not in comments[0]


@pytest.mark.asyncio
async def test_issue_terminal_normalization_fails_missing_branch_before_check(monkeypatch):
    calls = []

    async def fake_db_get_task(task_id):
        if calls and calls[-1][0] == 'update':
            return {
                'id': task_id,
                'status': 'failed',
                'error': calls[-1][2],
                'metadata': {'source': 'github-app', 'workflow_stage': 'code'},
            }
        return {
            'id': task_id,
            'status': 'completed',
            'metadata': {'source': 'github-app', 'workflow_stage': 'code'},
        }

    async def fake_update(task_id, status, worker_id=None, result=None, error=None):
        calls.append(('update', status, error))
        return True

    async def fake_context(task):
        return 'CodeTether/TetherScript', 12, 'codetether/issue-12', 'token'

    async def fake_verify(repo, branch, token):
        return {'branch_exists': False, 'has_commits': False, 'head_sha': '', 'error': '404 ref not found'}

    checks = []

    async def fake_check(task, *, status='completed'):
        checks.append((task['status'], task.get('error'), status))
        return 123

    async def fake_notify(task, worker_id=None):
        calls.append(('notify', task['status'], task.get('error')))

    monkeypatch.setattr('a2a_server.database.db_get_task', fake_db_get_task)
    monkeypatch.setattr('a2a_server.database.db_update_task_status', fake_update)
    monkeypatch.setattr(issue_final_comment, 'issue_task_context', fake_context)
    monkeypatch.setattr(issue_final_comment, '_verify_branch_and_commits', fake_verify)
    monkeypatch.setattr('a2a_server.github_app.checks.ensure_task_check_run', fake_check)
    monkeypatch.setattr('a2a_server.github_app.task_completion.notify_issue_task_completion', fake_notify)

    from a2a_server.github_app.task_status_hook import handle_github_app_terminal_task

    await handle_github_app_terminal_task('task-code')

    assert calls[0][0:2] == ('update', 'failed')
    assert 'Branch verification failed after worker completion' in calls[0][2]
    assert checks == [('failed', calls[0][2], 'completed')]
    assert calls[-1] == ('notify', 'failed', calls[0][2])
