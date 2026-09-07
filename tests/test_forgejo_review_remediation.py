"""Durable, session-resuming remediation for aggregated PR feedback."""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import asdict
from types import SimpleNamespace

import pytest

from fastapi import HTTPException, Request
from pydantic import ValidationError
from starlette import status

from a2a_server import forgejo_review_remediation as remediation
from a2a_server import monitor_api
from a2a_server.temporal import activities
from a2a_server.temporal.models import (
    ForgejoAgentWorkflowInput,
    ForgejoStageRequest,
)


HEAD = 'a' * 40
FORGEJO_TASK_ID = 81
REMEDIATION_PRIORITY = 500
TASK_TIMEOUT_SECONDS = 604_800


def request(**changes) -> remediation.ForgejoReviewRemediationRequest:
    """Return one valid remediation request with optional overrides."""
    values = {
        'repository': 'riley/spotlessbinco',
        'pull_request_number': 4932,
        'head_sha': HEAD,
        'prompt': 'Address every finding. Untrusted review markdown follows.',
        'target_agent_name': 'harvester-a2a-server-harvester-1',
        'resume_session_id': 'author-session-1',
        'context_id': 'forgejo_pr_4932_context',
        'author_provenance_id': 'ctprov_1234567890abcdef',
        'forgejo_author_login': 'spotless-agent',
        'git_signer': 'forgejo:spotless-agent',
        'blocking_findings': 1,
        'nonblocking_findings': 1,
        'finding_ids': ['chunk-1-finding-1', 'chunk-2-finding-1'],
    }
    values.update(changes)
    return remediation.ForgejoReviewRemediationRequest(**values)


@pytest.mark.asyncio
async def test_start_stores_prompt_in_forgejo_not_temporal(monkeypatch):
    created: list[dict] = []
    started: list[ForgejoAgentWorkflowInput] = []

    async def fake_create(**kwargs):
        created.append(kwargs)
        return {'id': 81, 'html_url': 'https://forge.example/agent/tasks/81'}

    async def fake_start(workflow_input):
        started.append(workflow_input)
        return 'forgejo-agent-task-81'

    monkeypatch.setattr(remediation, 'create_task', fake_create)
    monkeypatch.setattr(remediation, 'start_forgejo_workflow', fake_start)
    monkeypatch.setattr(
        remediation,
        'temporal_settings',
        lambda: SimpleNamespace(enabled=True),
    )

    result = await remediation.start_review_remediation(request())

    assert result['id'] == '81'
    assert result['workflow_id'] == 'forgejo-agent-task-81'
    assert created[0]['operation'] == 'review-remediation'
    assert created[0]['idempotency_key'] == f'review-remediation:{HEAD}'
    assert created[0]['metadata']['resume_session_id'] == 'author-session-1'
    assert created[0]['metadata']['review_finding_ids'] == [
        'chunk-1-finding-1',
        'chunk-2-finding-1',
    ]
    assert started[0].operation == 'review-remediation'
    assert started[0].forgejo_task_id == FORGEJO_TASK_ID
    temporal_payload = str(asdict(started[0])).lower()
    assert 'address every finding' not in temporal_payload
    assert 'review markdown' not in temporal_payload
    assert 'author-session-1' not in temporal_payload


@pytest.mark.asyncio
async def test_start_requires_temporal(monkeypatch):
    monkeypatch.setattr(
        remediation,
        'temporal_settings',
        lambda: SimpleNamespace(enabled=False),
    )

    with pytest.raises(RuntimeError, match='disabled'):
        await remediation.start_review_remediation(request())


def test_request_rejects_count_mismatch():
    with pytest.raises(ValidationError, match='finding count'):
        request(blocking_findings=2, nonblocking_findings=2)


@pytest.mark.parametrize(
    ('field', 'value'),
    [
        ('repository', '../outside'),
        ('head_sha', 'not-a-sha'),
        ('target_agent_name', 'worker name with spaces'),
        ('resume_session_id', '../../session'),
        ('author_provenance_id', 'unverified'),
        ('finding_ids', ['free-form-id']),
        ('finding_ids', ['chunk-1-finding-1', 'chunk-1-finding-1']),
    ],
)
def test_request_rejects_untrusted_routing_fields(field, value):
    with pytest.raises(ValidationError):
        request(**{field: value})


def http_request(token: str = '') -> Request:
    """Build the minimal Starlette request used by the ingest auth guard."""
    headers = []
    if token:
        headers.append((b'authorization', f'Bearer {token}'.encode()))
    return Request({'type': 'http', 'headers': headers})


@pytest.mark.asyncio
async def test_endpoint_rejects_missing_ingest_token(monkeypatch):
    monkeypatch.setattr(
        monitor_api, '_get_auth_tokens_set', lambda: {'correct-token'}
    )
    with pytest.raises(HTTPException) as error:
        await monitor_api.create_forgejo_review_remediation(
            http_request(), request()
        )
    assert error.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_endpoint_accepts_configured_ingest_token(monkeypatch):
    monkeypatch.setattr(
        monitor_api, '_get_auth_tokens_set', lambda: {'correct-token'}
    )
    received = []

    async def fake_start(value):
        received.append(value)
        return {
            'id': '81',
            'forgejo_task_id': FORGEJO_TASK_ID,
            'workflow_id': 'forgejo-agent-task-81',
        }

    monkeypatch.setattr(monitor_api, 'start_review_remediation', fake_start)
    result = await monitor_api.create_forgejo_review_remediation(
        http_request('correct-token'), request()
    )
    assert result['workflow_id'] == 'forgejo-agent-task-81'
    assert received[0].resume_session_id == 'author-session-1'


@pytest.mark.asyncio
async def test_activity_resumes_author_session_and_preserves_checklist(
    monkeypatch,
):
    dispatched: list[dict] = []
    updates: list[dict] = []
    forgejo_task = {
        'prompt': 'Fix every finding',
        'metadata': {
            'target_agent_name': 'harvester-a2a-server-harvester-1',
            'resume_session_id': 'author-session-1',
            'context_id': 'forgejo-pr-context',
            'review_finding_ids': [
                'chunk-1-finding-1',
                'chunk-2-finding-1',
            ],
            'review_blocking_findings': 1,
            'review_nonblocking_findings': 1,
            'provenance_verified': True,
            # Must never pass through the activity's explicit allowlist.
            'authorization': 'Bearer must-not-leak',
        },
    }

    async def fake_context(_request):
        return (
            forgejo_task,
            'funnel-fixes',
            HEAD,
            4932,
            'https://forge.example/riley/spotlessbinco.git',
            'funnel-fixes',
        )

    async def fake_create(**kwargs):
        dispatched.append(kwargs)
        return 'task-remediate-1'

    async def fake_update(**kwargs):
        updates.append(kwargs)
        return {'id': 81}

    async def fake_route():
        return {'model_ref': 'openai-codex/gpt-test'}

    @asynccontextmanager
    async def fake_ownership(request):
        yield

    async def fake_checkpoint(task_id):
        return {'id': task_id, 'metadata': dispatched[-1]['metadata']}

    monkeypatch.setattr(activities, '_execution_ownership', fake_ownership)
    monkeypatch.setattr(activities, '_codetether_task', fake_checkpoint)
    monkeypatch.setattr(activities, '_forgejo_context', fake_context)
    monkeypatch.setattr(
        'a2a_server.persistent_worker_pool.create_and_dispatch_task',
        fake_create,
    )
    monkeypatch.setattr(
        'a2a_server.forgejo_agent_client.update_task', fake_update
    )
    monkeypatch.setattr(
        'a2a_server.github_app.routing.resolve_task_target', fake_route
    )
    workflow = ForgejoAgentWorkflowInput(
        forgejo_task_id=81,
        repository='riley/spotlessbinco',
        issue_number=4932,
        pull_request_number=4932,
        workspace_id='global',
        branch='',
        head_sha=HEAD,
        operation='review-remediation',
    )

    result = await activities.dispatch_stage(
        ForgejoStageRequest(
            workflow=workflow,
            workflow_id='forgejo-agent-task-81',
            stage='remediate',
        )
    )

    assert result.task_id == 'task-remediate-1'
    assert dispatched[0]['priority'] == REMEDIATION_PRIORITY
    assert dispatched[0]['task_timeout_seconds'] == TASK_TIMEOUT_SECONDS
    assert dispatched[0]['metadata']['temporal_orchestrated'] is True
    assert dispatched[0]['metadata']['resume_session_id'] == 'author-session-1'
    assert dispatched[0]['metadata']['review_finding_ids'] == [
        'chunk-1-finding-1',
        'chunk-2-finding-1',
    ]
    assert 'authorization' not in dispatched[0]['metadata']
    assert updates[0]['status'] == 'running'
    assert updates[0]['external_task_id'] == 'task-remediate-1'
