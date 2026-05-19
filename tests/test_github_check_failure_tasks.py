import os

os.environ.setdefault('DATABASE_URL', 'postgresql://test:test@localhost:5432/test')

import pytest

from a2a_server.github_comment_tasks import (
    _check_failure_prompt,
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
    assert 'Details URL: https://github.com/owner/repo/actions/runs/1/job/2' in prompt
    assert metadata['source'] == 'github_check_failure_webhook'
    assert metadata['pr_number'] == 87
    assert metadata['check_name'] == 'Lint Code Base'
    assert metadata['source_metadata']['trigger'] == 'failed_check'


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
