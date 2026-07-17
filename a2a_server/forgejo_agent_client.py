"""Client for Forgejo's first-party repository coding-agent APIs."""

from __future__ import annotations

import hashlib
import json
import os

from collections.abc import Iterable, Mapping
from typing import Any
from urllib.parse import quote

import httpx


_SECRET_KEYS = {
    'access_token',
    'api_key',
    'apikey',
    'authorization',
    'cookie',
    'password',
    'passwd',
    'private_key',
    'refresh_token',
    'secret',
    'token',
}


def _setting(name: str, default: str = '') -> str:
    return os.environ.get(name, default).strip()


def _api_base(explicit: str = '') -> str:
    base = explicit.strip() or _setting('FORGEJO_API_URL')
    if not base:
        raise RuntimeError('FORGEJO_API_URL is not configured')
    return base.rstrip('/')


def _token() -> str:
    token = _setting('FORGEJO_TOKEN')
    if not token:
        raise RuntimeError('FORGEJO_TOKEN is not configured')
    return token


def _repo_path(repo: str) -> str:
    owner, name = repo.split('/', 1)
    return f'/repos/{quote(owner, safe="")}/{quote(name, safe="")}'


def _redact(value: Any, key: str = '') -> Any:
    normalized = key.lower().replace('-', '_')
    if normalized in _SECRET_KEYS:
        return '[REDACTED]'
    if isinstance(value, Mapping):
        return {
            str(child_key): _redact(child_value, str(child_key))
            for child_key, child_value in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


async def _request(
    method: str,
    path: str,
    *,
    base_url: str = '',
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.request(
            method,
            f'{_api_base(base_url)}{path}',
            headers={
                'Authorization': f'token {_token()}',
                'Accept': 'application/json',
            },
            json=_redact(payload) if payload is not None else None,
        )
    if response.status_code >= 400:
        detail = response.text[:400]
        raise RuntimeError(
            f'Forgejo agent API {method} {path} failed '
            f'({response.status_code}): {detail}'
        )
    data = response.json() if response.content else {}
    if not isinstance(data, dict):
        raise RuntimeError(f'Forgejo agent API {path} returned a non-object')
    return data


async def create_task(
    *,
    repo: str,
    operation: str,
    prompt: str,
    idempotency_key: str,
    issue_index: int = 0,
    pull_request_index: int = 0,
    head_sha: str = '',
    metadata: dict[str, Any] | None = None,
    base_url: str = '',
) -> dict[str, Any]:
    """Create or retrieve an idempotent Forgejo-owned coding-agent task."""
    return await _request(
        'POST',
        f'{_repo_path(repo)}/agent/tasks',
        base_url=base_url,
        payload={
            'operation': operation,
            'prompt': prompt,
            'issue_index': issue_index,
            'pull_request_index': pull_request_index,
            'head_sha': head_sha,
            'idempotency_key': idempotency_key,
            'metadata': metadata or {},
        },
    )


async def update_task(
    *,
    repo: str,
    task_id: int,
    base_url: str = '',
    **fields: Any,
) -> dict[str, Any]:
    """Update Forgejo task lifecycle or CodeTether linkage fields."""
    payload = {key: value for key, value in fields.items() if value is not None}
    return await _request(
        'PATCH',
        f'{_repo_path(repo)}/agent/tasks/{task_id}',
        base_url=base_url,
        payload=payload,
    )


async def append_event(
    *,
    repo: str,
    task_id: int,
    sequence: int,
    external_id: str,
    event_type: str,
    payload: dict[str, Any],
    base_url: str = '',
) -> dict[str, Any]:
    """Append one ordered, idempotent, redacted session event."""
    return await _request(
        'POST',
        f'{_repo_path(repo)}/agent/tasks/{task_id}/events',
        base_url=base_url,
        payload={
            'sequence': sequence,
            'external_id': external_id,
            'type': event_type,
            'payload': payload,
        },
    )


def _event_id(
    task_id: str, sequence: int, event_type: str, payload: Any
) -> str:
    serialized = json.dumps(payload, sort_keys=True, default=str)
    digest = hashlib.sha256(serialized.encode()).hexdigest()[:16]
    return f'{task_id}:{sequence}:{event_type}:{digest}'


def normalize_session_events(
    task_id: str,
    messages: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Normalize CodeTether messages and tool records into Forgejo events."""
    events: list[dict[str, Any]] = []
    sequence = 0
    for message in messages:
        sequence += 1
        message_payload = _redact(dict(message))
        event_type = 'agent.message'
        role = str(message.get('role') or '').lower()
        if role in {'user', 'human'}:
            event_type = 'user.message'
        elif role == 'system':
            event_type = 'system.message'
        events.append(
            {
                'sequence': sequence,
                'external_id': _event_id(
                    task_id, sequence, event_type, message_payload
                ),
                'type': event_type,
                'payload': message_payload,
            }
        )
        tool_calls = message.get('tool_calls') or []
        if isinstance(tool_calls, Mapping):
            tool_calls = [tool_calls]
        for tool_call in tool_calls:
            if not isinstance(tool_call, Mapping):
                continue
            sequence += 1
            tool_payload = _redact(dict(tool_call))
            tool_type = (
                'tool.result'
                if tool_payload.get('result') is not None
                or tool_payload.get('output') is not None
                else 'tool.call'
            )
            events.append(
                {
                    'sequence': sequence,
                    'external_id': _event_id(
                        task_id, sequence, tool_type, tool_payload
                    ),
                    'type': tool_type,
                    'payload': tool_payload,
                }
            )
    return events


async def publish_session_events(
    *,
    repo: str,
    forgejo_task_id: int,
    codetether_task_id: str,
    messages: Iterable[Mapping[str, Any]],
    base_url: str = '',
) -> int:
    """Publish a complete normalized transcript idempotently to Forgejo."""
    events = normalize_session_events(codetether_task_id, messages)
    for event in events:
        await append_event(
            repo=repo,
            task_id=forgejo_task_id,
            sequence=event['sequence'],
            external_id=event['external_id'],
            event_type=event['type'],
            payload=event['payload'],
            base_url=base_url,
        )
    return len(events)
