"""Signed, read-only CodeTether Agent session transcripts."""

# Recursive worker message/tool payloads are untyped JSON by contract.
# ruff: noqa: ANN401, E501

from __future__ import annotations

import hashlib
import hmac
import html
import json
import os
import time

from typing import Any
from urllib.parse import quote, urlencode

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse

from a2a_server import database as db
from a2a_server.monitor_api import _get_session_messages_impl


session_view_router = APIRouter(tags=['sessions'])

_DEFAULT_TTL_SECONDS = 7 * 24 * 60 * 60
_SECRET_KEYS = {
    'authorization',
    'cookie',
    'password',
    'passwd',
    'secret',
    'token',
    'api_key',
    'apikey',
    'private_key',
    'access_token',
    'refresh_token',
}


def _signing_secret() -> bytes:
    value = (
        os.getenv('CODETETHER_SESSION_VIEW_SECRET')
        or os.getenv('FORGEJO_WEBHOOK_SECRET')
        or ''
    )
    if not value:
        raise RuntimeError('session view signing secret is not configured')
    return value.encode()


def _signature(task_id: str, expires: int) -> str:
    message = f'{task_id}:{expires}'.encode()
    return hmac.new(_signing_secret(), message, hashlib.sha256).hexdigest()


def build_task_session_url(
    task_id: str,
    *,
    base_url: str | None = None,
    expires: int | None = None,
) -> str | None:
    """Build an expiring task-scoped session URL for Forgejo comments."""
    if not task_id:
        return None
    origin = (base_url or os.getenv('CODETETHER_PUBLIC_URL') or '').rstrip('/')
    if not origin:
        return None
    try:
        deadline = expires or int(time.time()) + int(
            os.getenv(
                'CODETETHER_SESSION_VIEW_TTL_SECONDS', _DEFAULT_TTL_SECONDS
            )
        )
        query = urlencode(
            {'expires': deadline, 'signature': _signature(task_id, deadline)}
        )
    except (RuntimeError, TypeError, ValueError):
        return None
    return f'{origin}/sessions/tasks/{quote(task_id, safe="")}?{query}'


def verify_task_session_signature(
    task_id: str, expires: int, signature: str
) -> None:
    """Reject expired or forged task-scoped session links."""
    if expires < int(time.time()):
        raise HTTPException(status_code=410, detail='Session link expired')
    try:
        expected = _signature(task_id, expires)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not signature or not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=403, detail='Invalid session link')


def _redact(value: Any, key: str = '') -> Any:
    """Recursively redact common credential fields before rendering."""
    if key.lower() in _SECRET_KEYS:
        return '[REDACTED]'
    if isinstance(value, dict):
        return {str(k): _redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, tuple):
        return [_redact(item) for item in value]
    return value


def _task_session_id(task: dict[str, Any]) -> str | None:
    metadata = task.get('metadata') or {}
    return (
        str(
            task.get('session_id')
            or metadata.get('session_id')
            or metadata.get('resume_session_id')
            or ''
        )
        or None
    )


async def _task_messages(
    task: dict[str, Any], limit: int
) -> tuple[str | None, list[dict[str, Any]]]:
    session_id = _task_session_id(task)
    if not session_id:
        return None, []
    workspace_id = str(
        task.get('workspace_id') or task.get('codebase_id') or ''
    )
    messages: list[dict[str, Any]] = []
    if workspace_id:
        try:
            merged = await _get_session_messages_impl(
                workspace_id, session_id, limit
            )
            messages = list(merged.get('messages') or [])
        except Exception:
            messages = []
    if not messages:
        messages = await db.db_list_messages(session_id=session_id, limit=limit)
    return session_id, [_redact(message) for message in messages]


def _json_block(value: Any) -> str:
    return html.escape(
        json.dumps(value, indent=2, ensure_ascii=False, default=str)
    )


def _tool_card(tool: Any) -> str:
    data = _redact(tool)
    name = 'Tool call'
    status = ''
    if isinstance(data, dict):
        name = str(
            data.get('name') or data.get('tool') or data.get('function') or name
        )
        status = str(data.get('status') or data.get('state') or '')
    title = html.escape(name + (f' · {status}' if status else ''))
    return f'<details class="tool"><summary>{title}</summary><pre>{_json_block(data)}</pre></details>'


def render_session_html(
    task: dict[str, Any], session_id: str | None, messages: list[dict[str, Any]]
) -> str:
    """Render a standalone, read-only CodeTether Agent transcript."""
    metadata = _redact(task.get('metadata') or {})
    repo = str(metadata.get('repo') or metadata.get('forgejo_repo') or '')
    number = metadata.get('pr_number') or metadata.get('issue_number')
    header_bits = [f'Task {html.escape(str(task.get("id") or ""))}']
    if repo:
        header_bits.append(html.escape(repo))
    if number:
        header_bits.append(f'#{html.escape(str(number))}')

    cards: list[str] = []
    for message in messages:
        role = html.escape(str(message.get('role') or 'event'))
        created = html.escape(str(message.get('created_at') or ''))
        content = html.escape(str(message.get('content') or ''))
        model = html.escape(str(message.get('model') or ''))
        tools = ''.join(
            _tool_card(call) for call in (message.get('tool_calls') or [])
        )
        cards.append(
            '<article class="message">'
            f'<header><strong>{role}</strong><span>{created}</span></header>'
            f'<div class="content">{content}</div>'
            f'{tools}'
            f'<footer>{("Model: " + model) if model else ""}</footer>'
            '</article>'
        )
    if not cards:
        cards.append(
            '<p class="empty">No persisted messages are available yet. Refresh while the agent is running.</p>'
        )

    status = html.escape(str(task.get('status') or 'unknown'))
    session_label = html.escape(session_id or 'pending')
    title = ' · '.join(header_bits)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>CodeTether Agent session</title>
<style>
:root{{--bg:#0d1117;--panel:#161b22;--border:#30363d;--text:#e6edf3;--muted:#8b949e;--accent:#58a6ff}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--text);font:14px/1.5 ui-sans-serif,system-ui,sans-serif}}
main{{max-width:1000px;margin:auto;padding:32px 20px}} h1{{font-size:24px;margin:0 0 8px}} .meta{{color:var(--muted);margin-bottom:24px}}
.message{{background:var(--panel);border:1px solid var(--border);border-radius:8px;margin:12px 0;padding:16px}}
.message header{{display:flex;justify-content:space-between;color:var(--accent)}} .message header span,.message footer{{color:var(--muted)}}
.content{{white-space:pre-wrap;overflow-wrap:anywhere;margin:14px 0}} details.tool{{border-top:1px solid var(--border);padding:10px 0}}
summary{{cursor:pointer;color:#d2a8ff}} pre{{overflow:auto;background:#010409;border-radius:6px;padding:12px;white-space:pre-wrap}}
.empty{{color:var(--muted)}}
</style></head><body><main>
<h1>CodeTether Agent · View session</h1>
<div class="meta">{title} · Status {status} · Session {session_label} · Read-only transcript</div>
{''.join(cards)}
</main></body></html>"""


@session_view_router.get(
    '/sessions/tasks/{task_id}', response_class=HTMLResponse
)
async def view_task_session(
    task_id: str,
    expires: int = Query(...),
    signature: str = Query(...),
    limit: int = Query(1000, ge=1, le=5000),
):
    """Render an expiring, task-scoped CodeTether Agent transcript."""
    verify_task_session_signature(task_id, expires, signature)
    task = await db.db_get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail='Task not found')
    session_id, messages = await _task_messages(task, limit)
    return HTMLResponse(
        render_session_html(task, session_id, messages),
        headers={
            'Cache-Control': 'private, no-store',
            'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'",
            'Referrer-Policy': 'no-referrer',
            'X-Content-Type-Options': 'nosniff',
        },
    )
