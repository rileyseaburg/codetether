import os

os.environ.setdefault(
    'DATABASE_URL', 'postgresql://test:test@localhost:5432/test'
)

import pytest

from a2a_server.github_comment_tasks import (
    _check_failure_prompt,
    _same_pr_worker_route,
    should_queue_check_failure_task,
)


@pytest.fixture
def repo_payload():
    return {
        'action': 'completed',
        'installation': {'id': 123},
        'repository': {
            'full_name': 'owner/repo',
            'name': 'repo',
            'clone_url': 'https://github.com/owner/repo.git',
            'owner': {'login': 'owner'},
        },
    }


def test_failed_check_run_on_pr_queues_remediation(repo_payload):
    payload = {
        **repo_payload,
        'check_run': {
            'id': 777,
            'name': 'Lint Code Base',
            'conclusion': 'failure',
            'details_url': 'https://github.com/owner/repo/actions/runs/1/job/2',
            'head_sha': 'abc123',
            'app': {'slug': 'github-actions', 'name': 'GitHub Actions'},
            'pull_requests': [
                {
                    'number': 87,
                    'url': 'https://api.github.com/repos/owner/repo/pulls/87',
                }
            ],
        },
    }

    assert should_queue_check_failure_task('check_run', payload)

    title, prompt, metadata = _check_failure_prompt(
        'check_run',
        payload,
        {
            'number': 87,
            'html_url': 'https://github.com/owner/repo/pull/87',
            'head': {'ref': 'codetether/issue-86', 'sha': 'abc123'},
        },
    )

    assert title == 'Fix failing PR #87 check: Lint Code Base'
    assert 'Branch: codetether/issue-86' in prompt
    assert (
        'Details URL: https://github.com/owner/repo/actions/runs/1/job/2'
        in prompt
    )
    assert metadata['source'] == 'github-app'
    assert metadata['workflow_stage'] == 'code'
    assert metadata['repo'] == 'owner/repo'
    assert metadata['pr_number'] == 87
    assert metadata['pr_head_sha'] == 'abc123'
    assert metadata['check_name'] == 'Lint Code Base'
    assert metadata['source_metadata']['trigger'] == 'failed_check'


def test_check_failure_prompt_includes_check_output(repo_payload):
    payload = {
        **repo_payload,
        'check_run': {
            'id': 777,
            'name': 'Playwright',
            'conclusion': 'failure',
            'output': {
                'summary': '[WebServer] [listMedia] Error: column "url" does not exist'
            },
            'pull_requests': [{'number': 87}],
        },
    }

    _, prompt, _ = _check_failure_prompt(
        'check_run',
        payload,
        {
            'number': 87,
            'html_url': 'https://github.com/owner/repo/pull/87',
            'head': {'ref': 'codetether/issue-86', 'sha': 'abc123'},
        },
    )

    assert 'Check output excerpt:' in prompt
    assert 'column "url" does not exist' in prompt


def test_success_check_run_does_not_queue(repo_payload):
    payload = {
        **repo_payload,
        'check_run': {
            'name': 'Run Tests',
            'conclusion': 'success',
            'pull_requests': [{'number': 87}],
        },
    }

    assert not should_queue_check_failure_task('check_run', payload)


def test_codetether_check_run_does_not_recurse(repo_payload):
    payload = {
        **repo_payload,
        'check_run': {
            'name': 'CodeTether / Build',
            'conclusion': 'failure',
            'app': {'slug': 'codetether', 'name': 'codetether'},
            'pull_requests': [{'number': 87}],
        },
    }

    assert not should_queue_check_failure_task('check_run', payload)


def test_failed_branch_check_without_pr_is_ignored(repo_payload):
    payload = {
        **repo_payload,
        'check_run': {
            'name': 'Lint Code Base',
            'conclusion': 'failure',
            'pull_requests': [],
        },
    }

    assert not should_queue_check_failure_task('check_run', payload)


@pytest.mark.asyncio
async def test_same_pr_worker_route_prefers_live_existing_worker(monkeypatch):
    class Conn:
        async def fetchrow(self, query, repo, pr, workspace_id):
            assert repo == 'owner/repo'
            assert pr == '87'
            assert workspace_id == 'workspace-1'
            return {'worker_id': 'worker-live', 'task_id': 'task-existing'}

    class Acquire:
        async def __aenter__(self):
            return Conn()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class Pool:
        def acquire(self):
            return Acquire()

    import a2a_server.github_comment_tasks as tasks

    async def fake_pool():
        return Pool()

    monkeypatch.setattr(tasks.db, 'get_pool', fake_pool)

    assert await _same_pr_worker_route('owner/repo', 87, 'workspace-1') == {
        'target_worker_id': 'worker-live',
        'worker_affinity': 'same_pr_worker',
        'worker_affinity_source_task_id': 'task-existing',
    }


@pytest.mark.asyncio
async def test_same_pr_worker_route_falls_back_without_live_worker(monkeypatch):
    class Conn:
        async def fetchrow(self, *args):
            return None

    class Acquire:
        async def __aenter__(self):
            return Conn()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class Pool:
        def acquire(self):
            return Acquire()

    import a2a_server.github_comment_tasks as tasks

    async def fake_pool():
        return Pool()

    monkeypatch.setattr(tasks.db, 'get_pool', fake_pool)

    assert await _same_pr_worker_route('owner/repo', 87, 'workspace-1') == {}
