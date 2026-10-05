"""Deterministic, non-sensitive Temporal workflow data contracts."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ForgejoAgentWorkflowInput:
    """Identifiers needed to orchestrate one Forgejo task attempt.

    Prompts, credentials, transcripts, tool payloads, and repository clone URLs
    are deliberately excluded from Temporal workflow history. Activities load
    those values from CodeTether/Forgejo using these identifiers.
    """

    forgejo_task_id: int
    repository: str
    issue_number: int
    pull_request_number: int
    workspace_id: str
    branch: str
    head_sha: str
    operation: str
    attempt: int = 1


@dataclass(frozen=True)
class ForgejoStageRequest:
    workflow: ForgejoAgentWorkflowInput
    workflow_id: str
    stage: str
    parent_task_id: str = ''
    review_task_id: str = ''
    fix_attempt: int = 0


@dataclass(frozen=True)
class ForgejoStageResult:
    task_id: str
    stage: str
    pull_request_number: int = 0
    branch: str = ''
    head_sha: str = ''


@dataclass(frozen=True)
class ForgejoTaskTerminalSignal:
    """Small terminal projection sent from CodeTether's task-status hook."""

    task_id: str
    stage: str
    status: str
    session_id: str = ''
    verdict: str = ''
    head_sha: str = ''
    pull_request_number: int = 0


@dataclass(frozen=True)
class ForgejoControlSignal:
    """Authenticated Forgejo control delivered to a running workflow."""

    action: str
    forgejo_task_id: int
    requested_by: str = ''
    request_id: str = ''


@dataclass
class ForgejoAgentWorkflowResult:
    """Terminal non-sensitive workflow result."""

    forgejo_task_id: int
    attempt: int
    status: str
    active_task_id: str = ''
    completed_stages: list[str] = field(default_factory=list)
    review_verdict: str = ''
    error_type: str = ''
