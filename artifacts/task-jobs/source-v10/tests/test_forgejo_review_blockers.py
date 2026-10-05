"""Review prerequisites must never become autonomous code or credential edits."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest

from temporalio.exceptions import ApplicationError

from a2a_server import forgejo_automation as automation
from a2a_server.forgejo_review_context import review_context
from a2a_server.temporal import activities
from a2a_server.temporal.models import (
    ForgejoAgentWorkflowInput,
    ForgejoStageRequest,
)


def parent(stage='fix'):
    return {
        'id': 'fix-1',
        'status': 'completed',
        'metadata': {
            'repo': 'owner/repo',
            'forgejo_api_url': 'https://forge.example/api/v1',
            'pr_number': 5901,
            'workspace_id': 'workspace',
            'branch_name': 'codetether/issue-5900',
            'pr_head_sha': 'unchanged-head',
            'workflow_stage': stage,
        },
    }


@pytest.mark.asyncio
async def test_blocked_review_does_not_attempt_credential_or_code_fix(
    monkeypatch,
):
    api = AsyncMock(side_effect=AssertionError('must not inspect or mutate'))
    monkeypatch.setattr(automation, 'forgejo_json', api)
    review = parent('review')
    review['result'] = 'BLOCKED: Vault returned 403; no code findings'
    assert await automation.create_forgejo_fix_followup(review) is None
    api.assert_not_awaited()


@pytest.mark.asyncio
async def test_unchanged_fix_reports_no_progress_not_missing_pr(monkeypatch):
    pr = {
        'number': 5901,
        'state': 'open',
        'head': {'sha': 'unchanged-head', 'ref': 'codetether/issue-5900'},
    }
    monkeypatch.setattr(automation, 'forgejo_json', AsyncMock(return_value=pr))
    with pytest.raises(automation.ForgejoReviewNotReady) as error:
        await automation.create_forgejo_review_task(parent())
    assert error.value.reason == 'review_fix_no_progress'
    body = activities._failure_explanation(
        {'status': 'failed', 'error_type': error.value.reason}
    )
    assert 'existing PR remains available' in body
    assert 'no open pull request' not in body


@pytest.mark.asyncio
async def test_duplicate_review_has_distinct_reason(monkeypatch):
    pr = {
        'number': 5901,
        'state': 'open',
        'head': {'sha': 'unchanged-head', 'ref': 'codetether/issue-5900'},
    }
    monkeypatch.setattr(automation, 'forgejo_json', AsyncMock(return_value=pr))
    monkeypatch.setattr(
        automation, '_task_exists', AsyncMock(return_value=True)
    )
    with pytest.raises(automation.ForgejoReviewNotReady) as error:
        await automation.create_forgejo_review_task(parent('code'))
    assert error.value.reason == 'review_already_exists'


@pytest.mark.asyncio
async def test_activity_preserves_nonretryable_reason(monkeypatch):
    monkeypatch.setattr(
        activities, '_codetether_task', AsyncMock(return_value=parent())
    )

    @asynccontextmanager
    async def ownership(request):
        yield

    monkeypatch.setattr(activities, '_execution_ownership', ownership)
    monkeypatch.setattr(
        automation,
        'create_forgejo_review_task',
        AsyncMock(
            side_effect=automation.ForgejoReviewNotReady(
                'review_fix_no_progress'
            )
        ),
    )
    request = ForgejoStageRequest(
        workflow_id='forgejo-agent-task-472',
        workflow=ForgejoAgentWorkflowInput(
            forgejo_task_id=472,
            repository='owner/repo',
            issue_number=5900,
            pull_request_number=5901,
            workspace_id='workspace',
            branch='codetether/issue-5900',
            head_sha='unchanged-head',
            operation='fix',
        ),
        stage='review',
        parent_task_id='fix-1',
    )
    with pytest.raises(ApplicationError) as error:
        await activities.dispatch_review(request)
    assert error.value.type == 'review_fix_no_progress'
    assert error.value.non_retryable


@pytest.mark.asyncio
async def test_review_receives_server_fetched_context_without_credentials():
    api = AsyncMock(
        side_effect=[
            [{'id': 1, 'body': 'Check the upsert conflict key'}],
            [{'context': 'tests', 'status': 'pending'}],
        ]
    )
    pr = {
        'number': 5901,
        'title': 'Fix snapshots',
        'head': {'sha': 'head'},
        'base': {'ref': 'main', 'sha': 'base'},
    }
    text = await review_context(
        api, 'https://forge.example/api/v1', 'owner/repo', pr
    )
    assert 'Check the upsert conflict key' in text
    assert '"status": "pending"' in text
    assert 'do not retrieve additional Vault tokens' in text
    assert (
        'CHANGES_REQUESTED only for specific actionable code findings' in text
    )
    assert api.await_count == 2


@pytest.mark.asyncio
async def test_evidence_failure_does_not_copy_exception_secret():
    text = await review_context(
        AsyncMock(side_effect=RuntimeError('secret-canary')),
        'https://forge.example/api/v1',
        'owner/repo',
        {'number': 1, 'head': {'sha': 'head'}},
    )
    assert 'secret-canary' not in text
    assert '"unavailable": true' in text
