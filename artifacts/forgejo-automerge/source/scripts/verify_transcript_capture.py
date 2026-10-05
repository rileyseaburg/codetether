"""Verify streamed worker output becomes a publishable session transcript.

Workers stream narration to the task-output endpoint but never sync session
messages, so the Forgejo "Session transcript" panel had no rows to publish. This
exercises `record_output_chunk` against the real schema, including the
`session_messages.session_id -> sessions.id` foreign key, then cleans up.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid

import asyncpg

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO_ROOT)

from a2a_server import forgejo_progress_events as progress  # noqa: E402


async def main() -> int:
    dsn = os.environ['DATABASE_URL']
    os.environ.setdefault('DATABASE_URL', dsn)

    task_id = str(uuid.uuid4())
    workspace_id = f'transcript-probe-{task_id[:8]}'
    derived_session = f'task-{task_id}'
    conn = await asyncpg.connect(dsn)
    failures: list[str] = []
    try:
        await conn.execute(
            """
            INSERT INTO tasks (id, workspace_id, title, prompt, agent_type,
                               status, priority, metadata)
            VALUES ($1, $2, 'transcript probe', 'probe', 'build',
                    'running', 100, $3::jsonb)
            """,
            task_id,
            workspace_id,
            json.dumps(
                {
                    'source': 'forgejo-webhook',
                    'forgejo_agent_task_id': 999999,
                    'repo': 'riley/probe',
                    'model_ref': 'openai-codex/gpt-5.6-sol-fast:max',
                }
            ),
        )

        wrote = await progress.record_output_chunk(
            task_id, 'Preparing the workspace and validating state.', 'wrk-probe'
        )
        print(f'wrote_first_chunk={wrote}')
        if not wrote:
            failures.append('first chunk was not persisted')

        # Blank output must not create rows.
        blank = await progress.record_output_chunk(task_id, '   ', 'wrk-probe')
        print(f'blank_chunk_ignored={not blank}')
        if blank:
            failures.append('blank chunk should be ignored')

        await progress.record_output_chunk(
            task_id, 'Committed and pushed the branch.', 'wrk-probe'
        )

        rows = await conn.fetch(
            'SELECT role, content FROM session_messages WHERE session_id = $1'
            ' ORDER BY created_at',
            derived_session,
        )
        print(f'transcript_rows={len(rows)}')
        if len(rows) != 2:
            failures.append(f'expected 2 transcript rows, got {len(rows)}')

        session_row = await conn.fetchrow(
            'SELECT id, workspace_id FROM sessions WHERE id = $1',
            derived_session,
        )
        print(f'parent_session_created={session_row is not None}')
        if session_row is None:
            failures.append('parent sessions row was not created')

        task_row = await conn.fetchrow(
            'SELECT metadata FROM tasks WHERE id = $1', task_id
        )
        metadata = task_row['metadata']
        if isinstance(metadata, str):
            metadata = json.loads(metadata or '{}')
        print(f'task_session_id={metadata.get("session_id")}')
        if metadata.get('session_id') != derived_session:
            failures.append('task metadata did not record the session id')

        # A non-Forgejo task must be ignored entirely.
        other_id = str(uuid.uuid4())
        await conn.execute(
            """
            INSERT INTO tasks (id, workspace_id, title, prompt, agent_type,
                               status, priority, metadata)
            VALUES ($1, $2, 'other probe', 'probe', 'build', 'running', 100,
                    '{"source":"github-app"}'::jsonb)
            """,
            other_id,
            workspace_id,
        )
        ignored = await progress.record_output_chunk(other_id, 'text', 'w')
        print(f'non_forgejo_ignored={not ignored}')
        if ignored:
            failures.append('non-Forgejo task should be ignored')
        await conn.execute('DELETE FROM tasks WHERE id = $1', other_id)

        if failures:
            for item in failures:
                print(f'FAILURE: {item}')
            return 1
        print('transcript_capture_ok=true')
        return 0
    finally:
        await conn.execute(
            'DELETE FROM session_messages WHERE session_id = $1',
            derived_session,
        )
        await conn.execute('DELETE FROM sessions WHERE id = $1', derived_session)
        await conn.execute('DELETE FROM tasks WHERE id = $1', task_id)
        await conn.close()


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
