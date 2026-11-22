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
