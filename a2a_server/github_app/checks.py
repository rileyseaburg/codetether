"""GitHub Checks API helpers for GitHub App task workflows."""

from __future__ import annotations

import html
import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .auth import github_json, installation_token

logger = logging.getLogger(__name__)

CheckStatus = Literal['queued', 'in_progress', 'completed']
CheckConclusion = Literal[
    'success', 'failure', 'neutral', 'cancelled', 'timed_out', 'action_required', 'skipped'
]
StatusState = Literal['error', 'failure', 'pending', 'success']

_VALID_STATUSES = {'queued', 'in_progress', 'completed'}
_PERMISSION_BLOCKER_FRAGMENT = 'Resource not accessible by integration'
_SECRET_MARKER = '[REDACTED]'
_TRUNCATED_MARKER = '\n\n… truncated for GitHub Checks output'
_TITLE_LIMIT = 80
_MAX_SUMMARY_CHARS = 60000
_MAX_TEXT_CHARS = 65000

_SECRET_PATTERNS = [
    re.compile(r'gh[opsru]_[A-Za-z0-9_]{20,}'),
    re.compile(r'github_pat_[A-Za-z0-9_]{20,}'),
    re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----', re.S),
    re.compile(r'(?i)(authorization|token|api[_-]?key|secret|password)\s*[:=]\s*\S+'),
]
_SENSITIVE_KEYS = {
    'authorization', 'password', 'passwd', 'secret', 'token', 'access_token', 'refresh_token',
    'api_key', 'apikey', 'github_token', 'private_key', 'prompt', 'raw_prompt', 'private_prompt',
    'args', 'arguments', 'result', 'results', 'stdout', 'stderr', 'output', 'raw', 'body', 'headers',
}
_SENSITIVE_QUERY_KEYS = {'token', 'access_token', 'refresh_token', 'api_key', 'apikey', 'password', 'secret', 'signature'}


@dataclass(slots=True)
class CheckTaskInfo:
    id: str = ''
    title: str = ''
    status: str = ''
    worker_id: str = ''


@dataclass(slots=True)
class CheckGitHubInfo:
    repo: str = ''
    issue_number: int | None = None
    pr_number: int | None = None
    workflow_stage: str | None = None


@dataclass(slots=True)
class CheckStep:
    name: str = ''
    status: str = ''
    conclusion: str = ''
    evidence: str = ''


@dataclass(slots=True)
class CheckToolCall:
    name: str = ''
    status: str = ''
    redacted: bool = True


@dataclass(slots=True)
class CheckEvidence:
    label: str = ''
    path: str = ''
    url: str = ''
    id: str = ''


@dataclass(slots=True)
class CheckSchema:
    schema_version: str = 'codetether.checks.v1'
    task: CheckTaskInfo = field(default_factory=CheckTaskInfo)
    github: CheckGitHubInfo = field(default_factory=CheckGitHubInfo)
    steps: list[CheckStep] = field(default_factory=list)
    tool_calls: list[CheckToolCall] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)
    evidence: list[CheckEvidence] = field(default_factory=list)
    redactions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def redact_secrets(value: Any) -> str:
    """Return a bounded string with common tokens/secrets removed."""
    text = _redact_url_credentials(str(value or ''))
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(lambda m: f'{m.group(1)}={_SECRET_MARKER}' if m.lastindex else _SECRET_MARKER, text)
    return text


def safe_markdown(value: Any, *, limit: int = 12000) -> str:
    """Render untrusted task text safely for GitHub markdown output."""
    return _truncate(html.escape(redact_secrets(value), quote=False).replace('\r\n', '\n').replace('\r', '\n'), limit)


def build_check_schema(task: dict[str, Any]) -> CheckSchema:
    """Build the structured, versioned, non-secret schema carried into check output."""
    metadata = task.get('metadata') or {}
    provenance = metadata.get('codetether_provenance') or metadata.get('policy_decision') or {}
    evidence = metadata.get('evidence') or metadata.get('validation_evidence') or []

    redactions: set[str] = set()
    return CheckSchema(
        task=CheckTaskInfo(
            id=_safe_str(task.get('id')),
            title=_safe_str(task.get('title')),
            status=_safe_str(task.get('status')),
            worker_id=_safe_str(task.get('worker_id')),
        ),
        github=CheckGitHubInfo(
            repo=_safe_str(metadata.get('repo')),
            issue_number=_safe_int(metadata.get('issue_number')),
            pr_number=_safe_int(metadata.get('pr_number')),
            workflow_stage=_safe_str(metadata.get('workflow_stage')) or None,
        ),
        steps=_normalize_steps(metadata.get('steps') or metadata.get('check_steps'), redactions),
        tool_calls=_normalize_tool_calls(metadata.get('tool_calls') or metadata.get('check_tool_calls'), redactions),
        provenance=_normalize_provenance(provenance, redactions),
        evidence=_normalize_evidence(evidence, redactions),
        redactions=sorted(redactions),
    )


def check_task_schema(task: dict[str, Any]) -> dict[str, Any]:
    """Return the check schema as a plain JSON-serializable dictionary."""
    return build_check_schema(task).to_dict()


def render_check_output(task: dict[str, Any]) -> dict[str, str]:
    """Create a safe GitHub Checks output object for a task."""
    schema = check_task_schema(task)
    title = _truncate(safe_markdown(schema['task']['title'] or 'CodeTether task', limit=_TITLE_LIMIT), _TITLE_LIMIT)
    status = schema['task']['status'] or 'unknown'
    task_id = schema['task']['id'] or 'unknown'
    stage = schema['github'].get('workflow_stage') or 'task'

    summary_parts = [
        f"### CodeTether {safe_markdown(stage, limit=80)} task",
        '',
        f"- Task: `{safe_markdown(task_id, limit=120)}`",
        f"- Status: `{safe_markdown(status, limit=80)}`",
    ]
    if schema['github'].get('pr_number'):
        summary_parts.append(f"- Pull request: `#{schema['github']['pr_number']}`")
    elif schema['github'].get('issue_number'):
        summary_parts.append(f"- Issue: `#{schema['github']['issue_number']}`")

    result_text = task.get('error') or task.get('result') or ''
    if result_text:
        summary_parts.extend(['', '#### Task output', safe_markdown(result_text, limit=8000)])

    if schema['steps']:
        summary_parts.extend(['', '#### Steps'])
        for step in schema['steps'][:20]:
            state = step.get('status') or step.get('conclusion') or ''
            summary_parts.append(f"- {safe_markdown(step.get('name') or 'step', limit=160)}" + (f" — `{safe_markdown(state, limit=40)}`" if state else ''))

    if schema['tool_calls']:
        summary_parts.extend(['', '#### Tool calls'])
        for call in schema['tool_calls'][:10]:
            summary_parts.append(f"- {safe_markdown(call.get('name') or 'tool', limit=120)} — details {_SECRET_MARKER}")

    if schema['evidence']:
        summary_parts.extend(['', '#### Evidence'])
        for item in schema['evidence'][:10]:
            label = item.get('label') or item.get('id') or 'evidence'
            path = item.get('path') or item.get('url') or item.get('id') or ''
            summary_parts.append(f"- {safe_markdown(label, limit=120)}" + (f": `{safe_markdown(path, limit=220)}`" if path else ''))

    text = '```json\n' + safe_markdown(_compact_schema(schema), limit=30000) + '\n```'
    return {
        'title': title,
        'summary': _truncate('\n'.join(summary_parts), _MAX_SUMMARY_CHARS),
        'text': _truncate(text, _MAX_TEXT_CHARS),
    }


def build_check_run_payload(task: dict[str, Any], *, status: CheckStatus = 'completed', include_head_sha: bool = False) -> dict[str, Any]:
    """Build and validate a GitHub Checks API payload."""
    if status not in _VALID_STATUSES:
        raise ValueError(f'Invalid GitHub check status: {status}')
    metadata = task.get('metadata') or {}
    payload: dict[str, Any] = {
        'name': _check_name(task),
        'status': status,
        'output': render_check_output(task),
        'details_url': _safe_details_url(metadata.get('github_issue_url'), metadata.get('repo')),
    }
    if include_head_sha:
        payload['head_sha'] = _head_sha(task)
    if status == 'completed':
        payload['conclusion'] = _conclusion_for_task(task)
        payload['completed_at'] = _timestamp(metadata.get('completed_at') or task.get('completed_at'))
    else:
        started_at = _timestamp(metadata.get('started_at') or task.get('started_at'))
        if started_at:
            payload['started_at'] = started_at
    return payload


async def ensure_task_check_run(task: dict[str, Any], *, status: CheckStatus = 'completed') -> int | None:
    """Create or update the GitHub check run for a GitHub App task.

    If the installation cannot create Checks API runs but can create legacy commit
    statuses, publish a status fallback so users still get non-mocked,
    commit-attached progress. Failures are logged and swallowed so task completion
    is never blocked.
    """
    metadata = task.get('metadata') or {}
    try:
        if metadata.get('source') != 'github-app':
            return None
        repo = _safe_str(metadata.get('repo')).strip()
        installation_id = metadata.get('github_installation_id')
        head_sha = _head_sha(task)
        if not repo or not installation_id or not head_sha:
            logger.info('Skipping GitHub check run for task %s: missing repo, installation id, or head sha', task.get('id'))
            return None

        token, _ = await installation_token(int(str(installation_id)))
        check_run_id = metadata.get('github_check_run_id')
        if check_run_id:
            payload = build_check_run_payload(task, status=status, include_head_sha=False)
            data = await github_json('PATCH', f'/repos/{repo}/check-runs/{int(check_run_id)}', token, payload)
            return int(data.get('id') or check_run_id)

        payload = build_check_run_payload(task, status=status, include_head_sha=True)
        try:
            data = await github_json('POST', f'/repos/{repo}/check-runs', token, payload)
        except Exception as exc:
            if _is_permission_blocker(exc):
                logger.warning(
                    'GitHub Checks API is not accessible for task %s; attempting commit status fallback. '
                    'Grant the GitHub App Checks: write permission for rich check runs. Error: %s',
                    task.get('id'),
                    exc,
                )
                fallback_id = await _ensure_commit_status_fallback(task, repo, head_sha, token, status=status)
                if fallback_id is not None:
                    return fallback_id
            raise
        new_id = int(data.get('id') or 0) or None
        if new_id:
            await _record_check_run_id(_safe_str(task.get('id')), new_id)
        return new_id
    except Exception as exc:
        if _is_permission_blocker(exc):
            logger.error(
                'GitHub status publishing is blocked for task %s: %s. '
                'Grant the GitHub App Checks: write permission, or Statuses: write for fallback commit statuses.',
                task.get('id'),
                exc,
            )
        else:
            logger.warning('GitHub Checks update failed for task %s: %s', task.get('id'), exc)
        return None


def build_commit_status_payload(task: dict[str, Any], *, status: CheckStatus = 'completed') -> dict[str, str]:
    """Build a legacy commit Statuses API fallback payload."""
    metadata = task.get('metadata') or {}
    return {
        'state': _status_state_for_task(task, status=status),
        'target_url': _safe_details_url(metadata.get('github_issue_url'), metadata.get('repo')),
        'description': _truncate(_status_description(task), 140),
        'context': _truncate(_check_name(task), 100),
    }


async def _ensure_commit_status_fallback(
    task: dict[str, Any],
    repo: str,
    head_sha: str,
    token: str,
    *,
    status: CheckStatus = 'completed',
) -> int | None:
    payload = build_commit_status_payload(task, status=status)
    try:
        data = await github_json('POST', f'/repos/{repo}/statuses/{head_sha}', token, payload)
    except Exception as exc:
        if _is_permission_blocker(exc):
            logger.error(
                'GitHub commit status fallback is not accessible for task %s: %s. '
                'Grant Statuses: write, or grant Checks: write for rich check runs.',
                task.get('id'),
                exc,
            )
        else:
            logger.warning('GitHub commit status fallback failed for task %s: %s', task.get('id'), exc)
        return None
    return int(data.get('id') or 0) or None


def _normalize_steps(value: Any, redactions: set[str]) -> list[CheckStep]:
    if not isinstance(value, list):
        return []
    steps = []
    for idx, step in enumerate(value[:50], start=1):
        if isinstance(step, dict):
            steps.append(CheckStep(
                name=_safe_str(_redact_recursive(step.get('name') or step.get('title') or f'Step {idx}', redactions)),
                status=_safe_str(_redact_recursive(step.get('status'), redactions)),
                conclusion=_safe_str(_redact_recursive(step.get('conclusion'), redactions)),
                evidence=_safe_str(_redact_recursive(step.get('evidence') or step.get('path') or step.get('url'), redactions)),
            ))
        else:
            steps.append(CheckStep(name=_safe_str(_redact_recursive(step, redactions))))
    return steps


def _normalize_tool_calls(value: Any, redactions: set[str]) -> list[CheckToolCall]:
    if not isinstance(value, list):
        return []
    calls = []
    for idx, call in enumerate(value[:50], start=1):
        if isinstance(call, dict):
            if any(k in call for k in ('args', 'arguments', 'result', 'results', 'output', 'stdout', 'stderr')):
                redactions.add('tool_call_details')
            calls.append(CheckToolCall(
                name=_safe_str(_redact_recursive(call.get('name') or call.get('tool') or f'tool-{idx}', redactions)),
                status=_safe_str(_redact_recursive(call.get('status') or call.get('conclusion'), redactions)),
                redacted=True,
            ))
        else:
            calls.append(CheckToolCall(name=_safe_str(_redact_recursive(call, redactions)), redacted=True))
    return calls


def _normalize_provenance(value: Any, redactions: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    allowed = {'origin', 'actor', 'intent', 'policy', 'decision', 'reason', 'workflow', 'run_id', 'commit', 'sha', 'ap_origin'}
    return {str(k): _redact_recursive(v, redactions) for k, v in value.items() if str(k).lower() in allowed}


def _normalize_evidence(value: Any, redactions: set[str]) -> list[CheckEvidence]:
    if isinstance(value, dict):
        value = [value]
    if not isinstance(value, list):
        return []
    evidence = []
    for item in value[:20]:
        if isinstance(item, dict):
            evidence.append(CheckEvidence(
                label=_safe_str(_redact_recursive(item.get('label') or item.get('name') or item.get('type'), redactions)),
                path=_safe_str(_redact_recursive(item.get('path'), redactions)),
                url=_safe_str(_redact_recursive(item.get('url'), redactions)),
                id=_safe_str(_redact_recursive(item.get('id'), redactions)),
            ))
        else:
            evidence.append(CheckEvidence(label=_safe_str(_redact_recursive(item, redactions))))
    return evidence


def _redact_recursive(value: Any, redactions: set[str]) -> Any:
    if isinstance(value, dict):
        out = {}
        for key, child in value.items():
            key_s = str(key)
            if key_s.lower() in _SENSITIVE_KEYS:
                out[key_s] = _SECRET_MARKER
                redactions.add(key_s.lower())
            else:
                out[key_s] = _redact_recursive(child, redactions)
        return out
    if isinstance(value, list):
        return [_redact_recursive(v, redactions) for v in value[:50]]
    if isinstance(value, str):
        redacted = redact_secrets(value)
        if redacted != value:
            redactions.add('secret_pattern')
        return redacted
    return value


def _redact_url_credentials(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        raw = match.group(0)
        try:
            parts = urlsplit(raw)
            netloc = parts.hostname or ''
            if parts.port:
                netloc += f':{parts.port}'
            query = urlencode([(k, _SECRET_MARKER if k.lower() in _SENSITIVE_QUERY_KEYS else v) for k, v in parse_qsl(parts.query, keep_blank_values=True)])
            if parts.username or parts.password:
                netloc = f'{_SECRET_MARKER}@{netloc}'
            return urlunsplit((parts.scheme, netloc, parts.path, query, parts.fragment))
        except Exception:
            return _SECRET_MARKER

    return re.sub(r'https?://[^\s`<>)]+', repl, text)


def _safe_details_url(url: Any, repo: Any) -> str:
    safe_url = redact_secrets(url) if url else ''
    return safe_url or f'https://github.com/{_safe_str(repo)}'


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    keep = max(0, limit - len(_TRUNCATED_MARKER))
    return text[:keep].rstrip() + _TRUNCATED_MARKER


def _safe_str(value: Any) -> str:
    if value is None:
        return ''
    return redact_secrets(value)


def _safe_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None and str(value).strip() else None
    except (TypeError, ValueError):
        return None


def _compact_schema(schema: dict[str, Any]) -> str:
    return json.dumps(schema, indent=2, sort_keys=True)


def _check_name(task: dict[str, Any]) -> str:
    metadata = task.get('metadata') or {}
    stage = metadata.get('workflow_stage') or task.get('agent_type') or 'task'
    return _truncate(f'CodeTether / {safe_markdown(stage, limit=60)}', 100)


def _conclusion_for_task(task: dict[str, Any]) -> CheckConclusion:
    status = _safe_str(task.get('status')).lower()
    mapping: dict[str, CheckConclusion] = {
        'completed': 'success',
        'success': 'success',
        'failed': 'failure',
        'failure': 'failure',
        'error': 'failure',
        'cancelled': 'cancelled',
        'canceled': 'cancelled',
        'timed_out': 'timed_out',
        'timeout': 'timed_out',
        'skipped': 'skipped',
        'neutral': 'neutral',
    }
    return mapping.get(status, 'neutral')


def _head_sha(task: dict[str, Any]) -> str:
    metadata = task.get('metadata') or {}
    return _safe_str(metadata.get('github_check_head_sha') or metadata.get('pr_head_sha') or metadata.get('head_sha')).strip()




def _status_state_for_task(task: dict[str, Any], *, status: CheckStatus = 'completed') -> StatusState:
    if status != 'completed':
        return 'pending'
    conclusion = _conclusion_for_task(task)
    if conclusion == 'success':
        return 'success'
    if conclusion in {'failure', 'timed_out', 'cancelled', 'action_required'}:
        return 'failure'
    return 'error'


def _status_description(task: dict[str, Any]) -> str:
    metadata = task.get('metadata') or {}
    stage = _safe_str(metadata.get('workflow_stage') or task.get('agent_type') or 'task')
    status = _safe_str(task.get('status') or 'unknown')
    task_id = _safe_str(task.get('id') or 'unknown')
    return f'CodeTether {stage} task {task_id} is {status}'


def _is_permission_blocker(exc: Exception) -> bool:
    return _PERMISSION_BLOCKER_FRAGMENT in str(exc)

def _timestamp(value: Any) -> str | None:
    if value is None:
        return datetime.now(timezone.utc).isoformat()
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    text = _safe_str(value).strip()
    return text or None


async def _record_check_run_id(task_id: str, check_run_id: int) -> None:
    if not task_id:
        return
    try:
        from .. import database as db

        pool = await db.get_pool()
        if not pool:
            return
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE tasks
                SET metadata = COALESCE(metadata, '{}'::jsonb) || $2::jsonb,
                    updated_at = NOW()
                WHERE id = $1
                """,
                task_id,
                json.dumps({'github_check_run_id': check_run_id}),
            )
    except Exception as exc:
        logger.warning('Failed to persist GitHub check_run_id for task %s: %s', task_id, exc)
