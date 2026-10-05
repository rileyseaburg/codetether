"""Verify a typed worker event survives storage and publishes as a tool event.

Reproduces the real path: the worker streams a `tool.result` event, the server
stores it, and `normalize_session_events` classifies it. Previously the tool
name and status were flattened into text and every entry published as
`agent.message`, so Forgejo could never render a tool card.

The scratch task, session, and message rows are always removed.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid

from pathlib import Path

import asyncpg


_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from a2a_server import forgejo_progress_events as progress  # noqa: E402
from a2a_server.forgejo_agent_client import (  # noqa: E402
    normalize_session_events,
)


def _messages(rows: list[asyncpg.Record]) -> list[dict]:
    """Convert database records to the message projection under test."""
    messages = []
    for row in rows:
        tool_calls = row['tool_calls']
        if isinstance(tool_calls, str):
            tool_calls = json.loads(tool_calls or 'null')
        messages.append(
            {
                'role': row['role'],
                'content': row['content'],
                'tool_calls': tool_calls or [],
            }
        )
    return messages


def _event_failures(events: list[dict]) -> list[str]:
    """Return all failed round-trip invariants without short-circuiting."""
    failures = []
    counts: dict[str, int] = {}
    for event in events:
        counts[event['type']] = counts.get(event['type'], 0) + 1
    print(f'published_types={json.dumps(counts, sort_keys=True)}')
    expected = {
        'tool.call': 'no tool.call event was published',
        'tool.result': 'no tool.result event was published',
        'agent.reasoning': 'no agent.reasoning event was published',
    }
    failures.extend(
        message
        for kind, message in expected.items()
        if not counts.get(kind)
    )

    tool_events = [
        event
        for event in events
        if event['type'] in {'tool.call', 'tool.result'}
    ]
    failures.extend(
        'tool name did not survive storage'
        for event in tool_events
        if event['payload'].get('name') != 'bash'
    )
    failures.extend(
        'internal marker leaked into the payload'
        for event in tool_events
        if 'codetether_event_type' in event['payload']
    )
    calls = [event for event in events if event['type'] == 'tool.call']
    command = (
        calls[0]['payload'].get('arguments', {}).get('command')
        if calls
        else None
    )
    if command != 'ls -la':
        failures.append('tool arguments did not survive storage')
    return failures


async def main() -> int:
    """Run the database-backed typed-event round-trip probe."""
    dsn = os.environ['DATABASE_URL']
    task_id = str(uuid.uuid4())
    session_id = f'task-{task_id}'
    conn = await asyncpg.connect(dsn)
    failures: list[str] = []
    try:
        await conn.execute(
            """
            INSERT INTO tasks (id, workspace_id, title, prompt, agent_type,
                               status, priority, metadata)
            VALUES ($1, $2, 'typed event probe', 'probe', 'build',
                    'running', 100, $3::jsonb)
            """,
            task_id,
            f'typed-probe-{task_id[:8]}',
            json.dumps(
                {
                    'source': 'forgejo-webhook',
                    'forgejo_agent_task_id': 999999,
                    'repo': 'riley/probe',
                    'model_ref': 'openai-codex/gpt-5.6-luna-fast:max',
                }
            ),
        )

        wrote_call = await progress.record_output_chunk(
            task_id,
            '[tool:start:bash]',
            'probe',
            {
                'type': 'tool.call',
                'payload': {
                    'name': 'bash',
                    'status': 'started',
                    'arguments': {'command': 'ls -la'},
                },
            },
        )
        wrote_result = await progress.record_output_chunk(
            task_id,
            '[tool:bash:ok] total 12',
            'probe',
            {
                'type': 'tool.result',
                'payload': {
                    'name': 'bash',
                    'status': 'ok',
                    'success': True,
                    'output': 'total 12',
                    'output_truncated': False,
                },
            },
        )
        wrote_reasoning = await progress.record_output_chunk(
            task_id,
            'Checking the failing test first.',
            'probe',
            {
                'type': 'agent.reasoning',
                'payload': {
                    'role': 'assistant',
                    'content': 'Checking the failing test first.',
                },
            },
        )
        print(f'wrote_call={wrote_call}')
        print(f'wrote_result={wrote_result}')
        print(f'wrote_reasoning={wrote_reasoning}')
        for label, ok in (
            ('call', wrote_call),
            ('result', wrote_result),
            ('reasoning', wrote_reasoning),
        ):
            if not ok:
                failures.append(f'{label} chunk was not persisted')

        rows = await conn.fetch(
            'SELECT role, content, tool_calls FROM session_messages'
            ' WHERE session_id = $1 ORDER BY created_at',
            session_id,
        )
        print(f'stored_rows={len(rows)}')

        events = normalize_session_events(task_id, _messages(rows))
        failures.extend(_event_failures(events))

        if failures:
            for item in failures:
                print(f'FAILURE: {item}')
            return 1
        print('typed_event_roundtrip_ok=true')
        return 0
    finally:
        await conn.execute(
            'DELETE FROM session_messages WHERE session_id = $1', session_id
        )
        await conn.execute('DELETE FROM sessions WHERE id = $1', session_id)
        await conn.execute('DELETE FROM tasks WHERE id = $1', task_id)
        await conn.close()


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
