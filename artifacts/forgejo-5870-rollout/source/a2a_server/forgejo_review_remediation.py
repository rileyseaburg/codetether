"""Start durable Temporal remediation for an aggregated Forgejo PR review.

The Forgejo Action creates one request per immutable PR head. The full prompt
and finding checklist are stored in Forgejo's native agent task, while Temporal
history receives only non-sensitive identifiers. Retries therefore remain
durable without copying review content, credentials, or transcripts into
workflow history.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator, model_validator

from a2a_server.forgejo_agent_client import create_task
from a2a_server.temporal.client import start_forgejo_workflow
from a2a_server.temporal.config import temporal_settings
from a2a_server.temporal.models import ForgejoAgentWorkflowInput


_REPOSITORY = re.compile(
    r'^[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*$'
)
_HEAD_SHA = re.compile(r'^[0-9a-fA-F]{40}$')
_IDENTIFIER = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:@-]{0,127}$')
_FINDING_ID = re.compile(r'^chunk-[1-9][0-9]*-finding-[1-9][0-9]*$')


class ForgejoReviewRemediationRequest(BaseModel):
    """Trusted orchestration fields produced by the base-branch Action."""

    repository: str = Field(min_length=3, max_length=255)
    pull_request_number: int = Field(ge=1)
    head_sha: str = Field(min_length=40, max_length=40)
    prompt: str = Field(min_length=1, max_length=500_000)
    target_agent_name: str = Field(min_length=1, max_length=128)
    resume_session_id: str = Field(min_length=1, max_length=128)
    context_id: str = Field(min_length=1, max_length=128)
    author_provenance_id: str = Field(min_length=23, max_length=87)
    forgejo_author_login: str = Field(min_length=1, max_length=128)
    git_signer: str = Field(min_length=1, max_length=255)
    blocking_findings: int = Field(ge=0, le=1000)
    nonblocking_findings: int = Field(ge=0, le=1000)
    finding_ids: list[str] = Field(min_length=1, max_length=2000)

    @field_validator('repository')
    @classmethod
    def valid_repository(cls, value: str) -> str:
        """Reject paths and URLs masquerading as repository names."""
        if not _REPOSITORY.fullmatch(value):
            raise ValueError('repository must be owner/name')
        return value

    @field_validator('head_sha')
    @classmethod
    def valid_head_sha(cls, value: str) -> str:
        """Require the exact immutable Git object identifier."""
        if not _HEAD_SHA.fullmatch(value):
            raise ValueError('head_sha must be a 40-character hexadecimal SHA')
        return value.lower()

    @field_validator(
        'target_agent_name',
        'resume_session_id',
        'context_id',
        'forgejo_author_login',
    )
    @classmethod
    def valid_identifier(cls, value: str) -> str:
        """Bound routing identifiers to the worker-safe character set."""
        if not _IDENTIFIER.fullmatch(value):
            raise ValueError('invalid routing identifier')
        return value

    @field_validator('author_provenance_id')
    @classmethod
    def valid_provenance(cls, value: str) -> str:
        """Require a CodeTether provenance identifier."""
        if not re.fullmatch(r'ctprov_[A-Za-z0-9_-]{16,80}', value):
            raise ValueError('invalid CodeTether provenance identifier')
        return value

    @field_validator('finding_ids')
    @classmethod
    def valid_finding_ids(cls, value: list[str]) -> list[str]:
        """Require unique, stable checklist identifiers."""
        if len(value) != len(set(value)):
            raise ValueError('finding IDs must be unique')
        if not all(_FINDING_ID.fullmatch(item) for item in value):
            raise ValueError('invalid finding ID')
        return value

    @model_validator(mode='after')
    def complete_checklist(self) -> ForgejoReviewRemediationRequest:
        """Fail when finding counts and checklist cardinality diverge."""
        expected = self.blocking_findings + self.nonblocking_findings
        if expected != len(self.finding_ids):
            raise ValueError('finding count does not match finding_ids')
        return self


async def start_review_remediation(
    request: ForgejoReviewRemediationRequest,
) -> dict[str, object]:
    """Create the native Forgejo task and start its idempotent workflow."""
    if not temporal_settings().enabled:
        raise RuntimeError('Forgejo Temporal orchestration is disabled')

    metadata = {
        'source': 'forgejo-pr-review',
        'workflow_stage': 'remediate',
        'target_agent_name': request.target_agent_name,
        'resume_session_id': request.resume_session_id,
        'context_id': request.context_id,
        'conversation_id': request.context_id,
        'author_provenance_id': request.author_provenance_id,
        'forgejo_author_login': request.forgejo_author_login,
        'git_signer': request.git_signer,
        'review_blocking_findings': request.blocking_findings,
        'review_nonblocking_findings': request.nonblocking_findings,
        'review_finding_ids': request.finding_ids,
        'preserve_session_workspace': True,
        'provenance_verified': True,
    }
    task = await create_task(
        repo=request.repository,
        operation='review-remediation',
        prompt=request.prompt,
        pull_request_index=request.pull_request_number,
        head_sha=request.head_sha,
        idempotency_key=f'review-remediation:{request.head_sha}',
        metadata=metadata,
    )
    forgejo_task_id = int(task.get('id') or 0)
    if forgejo_task_id < 1:
        raise RuntimeError('Forgejo did not return a task identifier')

    workflow_id = await start_forgejo_workflow(
        ForgejoAgentWorkflowInput(
            forgejo_task_id=forgejo_task_id,
            repository=request.repository,
            issue_number=request.pull_request_number,
            pull_request_number=request.pull_request_number,
            workspace_id='global',
            branch='',
            head_sha=request.head_sha,
            operation='review-remediation',
        )
    )
    return {
        'id': str(forgejo_task_id),
        'forgejo_task_id': forgejo_task_id,
        'workflow_id': workflow_id,
        'html_url': str(task.get('html_url') or ''),
    }
