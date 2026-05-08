import pytest

from a2a_server.github_app import issue_final_comment, issue_review_task, task_completion, task_context


@pytest.fixture
def pr_payload():
    return {
        'number': 77,
        'html_url': 'https://github.com/acme/widgets/pull/77',
        'head': {'sha': 'abc123'},
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
    assert 'github:review_pr' in provenance['ap_delegation']['chain'][1]['capability']['operations']


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
    assert 'action outside delegated capability envelope' in decision['provenance']['failures']


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
    monkeypatch.setattr(issue_final_comment, '_verify_branch_and_commits', fake_verify)
    monkeypatch.setattr(issue_final_comment, 'open_issue_pr', fake_open_pr)
    monkeypatch.setattr(issue_final_comment, 'post_issue_comment', fake_post)
    monkeypatch.setattr(issue_review_task, 'create_issue_review_task', fake_create_review_task)

    await issue_final_comment.notify_issue_final_comment({
        'id': 'task-code',
        'status': 'completed',
        'result': 'done',
        'metadata': {
            'workspace_id': 'ws1',
            'github_issue_url': 'https://github.com/acme/widgets/issues/12',
            'github_installation_id': 123,
            'target_worker_id': 'wrk1',
        },
    })

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
    monkeypatch.setattr(issue_review_task, 'create_issue_merge_task', fake_create_merge_task)

    task = {
        'id': 'task-review-1',
        'title': 'Review issue PR #77',
        'status': 'completed',
        'metadata': {'source': 'github-app', 'workflow_stage': 'review'},
    }

    await task_completion.notify_issue_task_completion(task)

    assert calls == [(task, 'token')]


@pytest.mark.asyncio
async def test_create_review_task_records_allow_decision_without_builder_target(monkeypatch, pr_payload):
    created = []
    decisions = []

    async def fake_dispatch(**kwargs):
        created.append(kwargs)
        return 'task-review-1'

    async def fake_record(**kwargs):
        decisions.append(kwargs)

    monkeypatch.setattr('a2a_server.persistent_worker_pool.create_and_dispatch_task', fake_dispatch)
    monkeypatch.setattr(issue_review_task, 'record_automation_decision', fake_record)

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
    assert decisions[0]['decision']['allowed'] is True
    assert decisions[0]['task_id'] == 'task-review-1'


@pytest.mark.asyncio
async def test_create_review_task_records_deny_decision(monkeypatch, pr_payload):
    decisions = []

    def fake_policy(provenance, action):
        return {'allowed': False, 'action': action, 'provenance': {'failures': ['denied']}}

    async def fake_record(**kwargs):
        decisions.append(kwargs)

    monkeypatch.setattr(issue_review_task, 'policy_decision', fake_policy)
    monkeypatch.setattr(issue_review_task, 'record_automation_decision', fake_record)

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
@pytest.mark.parametrize('review_result', ['CHANGES_REQUESTED: tests failed', 'BLOCKED: provenance mismatch', 'completed without verdict'])
async def test_create_merge_task_requires_explicit_approval(monkeypatch, review_result):
    called = False

    async def fake_github_json(*args, **kwargs):
        nonlocal called
        called = True
        return {}

    monkeypatch.setattr('a2a_server.github_app.auth.github_json', fake_github_json)

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
    assert called is False


def test_reviewer_approval_ignores_blocked_prose():
    assert issue_review_task.reviewer_allows_merge({
        'result': (
            'Self-approval is blocked by GitHub, so I left an approving comment instead.\n'
            '## Final Verdict: **APPROVED**\n\n'
            'Validation passed.'
        )
    }) is True


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

    monkeypatch.setattr('a2a_server.github_app.auth.github_json', fake_github_json)
    monkeypatch.setattr(issue_review_task, 'record_automation_decision', fake_record)
    monkeypatch.setattr('a2a_server.github_app.watch.post_issue_comment', fake_post)

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
    assert 'PR head SHA changed' in decisions[0]['decision']['provenance']['failures'][0]
    assert 'Blocked because the PR changed' in comments[0][2]


@pytest.mark.asyncio
async def test_create_merge_task_blocks_unresolved_review_feedback(monkeypatch, pr_payload):
    decisions = []
    comments = []

    async def fake_github_json(method, path, token):
        if path == '/repos/acme/widgets/pulls/77':
            return pr_payload
        raise AssertionError(f'unexpected GitHub call: {method} {path}')

    async def fake_feedback_status(repo, pr_number, token):
        return {
            'feedback_addressed': False,
            'blockers': ['Unresolved review thread at src/app.py:10 by reviewer'],
        }

    async def fake_record(**kwargs):
        decisions.append(kwargs)

    async def fake_post(repo, issue_number, token, body):
        comments.append(body)

    monkeypatch.setattr('a2a_server.github_app.auth.github_json', fake_github_json)
    monkeypatch.setattr(issue_review_task, 'review_feedback_status', fake_feedback_status)
    monkeypatch.setattr(issue_review_task, 'record_automation_decision', fake_record)
    monkeypatch.setattr('a2a_server.github_app.watch.post_issue_comment', fake_post)

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
    assert 'Unresolved review thread' in decisions[0]['decision']['provenance']['failures'][0]
    assert 'review feedback is not fully addressed' in comments[0]


@pytest.mark.asyncio
async def test_create_merge_task_auto_merges_when_feedback_addressed(monkeypatch, pr_payload):
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

    async def fake_record(**kwargs):
        decisions.append(kwargs)

    async def fake_post(repo, issue_number, token, body):
        comments.append(body)

    monkeypatch.setattr('a2a_server.github_app.auth.github_json', fake_github_json)
    monkeypatch.setattr(issue_review_task, 'review_feedback_status', fake_feedback_status)
    monkeypatch.setattr(issue_review_task, 'record_automation_decision', fake_record)
    monkeypatch.setattr('a2a_server.github_app.watch.post_issue_comment', fake_post)

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
    assert any(call[1] == '/repos/acme/widgets/pulls/77/merge' for call in calls)
    assert decisions[-1]['decision']['allowed'] is True
    assert 'Merged PR #77 using `squash`' in comments[0]


@pytest.mark.asyncio
async def test_create_merge_task_enables_github_auto_merge_when_direct_merge_blocked(monkeypatch, pr_payload):
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
            raise RuntimeError('Repository rule violations found: Cannot update this protected ref.')
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

    async def fake_record(**kwargs):
        decisions.append(kwargs)

    async def fake_post(repo, issue_number, token, body):
        comments.append(body)

    monkeypatch.setattr('a2a_server.github_app.auth.github_json', fake_github_json)
    monkeypatch.setattr('a2a_server.github_app.auth.github_graphql', fake_github_graphql)
    monkeypatch.setattr(issue_review_task, 'review_feedback_status', fake_feedback_status)
    monkeypatch.setattr(issue_review_task, 'record_automation_decision', fake_record)
    monkeypatch.setattr('a2a_server.github_app.watch.post_issue_comment', fake_post)

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


def test_merge_provenance_uses_merge_steward_actor(pr_payload):
    provenance = issue_review_task.issue_pr_provenance(
        repo='acme/widgets',
        issue_number=12,
        branch='codetether/issue-12',
        pr=pr_payload,
        installation_id=123,
        action='github:merge_pr',
    )

    assert provenance['ap_delegation']['chain'][1]['actor'] == 'codetether-merge-steward'
