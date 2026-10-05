"""The terminal hook must act on the released status, not a stale read.

An orchestrated Forgejo task stalled after its `prepare` stage completed: the
`code` stage was never dispatched and the Temporal workflow sat on its 7-day
timer. The release handler writes the terminal status and calls the hook
concurrently, so `db_get_task` could still return the previous non-terminal
status, and the workflow signal reported a non-terminal stage.
"""

from __future__ import annotations

import pytest

from a2a_server.github_app import task_status_hook as hook

TASK_ID = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'


def _forgejo_task(status: str) -> dict:
    return {
        'id': TASK_ID,
        'status': status,
        'metadata': {
            'source': 'forgejo-webhook',
            'workflow_stage': 'prepare',
            'temporal_orchestrated': True,
            'forgejo_agent_task_id': 33,
            'repo': 'codetether-bot/forgejo-codetether-agent',
            'issue_number': 18,
        },
    }


@pytest.fixture
def captured(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    seen: list[dict] = []

    async def _notify(task):
        seen.append(task)

    monkeypatch.setattr(
        'a2a_server.forgejo_task_completion.notify_forgejo_task_completion',
        _notify,
    )
    return seen


@pytest.mark.asyncio
async def test_released_status_overrides_stale_database_read(
    monkeypatch: pytest.MonkeyPatch, captured: list[dict]
) -> None:
    async def _get_task(_task_id):
        # The status write has not landed yet.
        return _forgejo_task('running')

    monkeypatch.setattr('a2a_server.database.db_get_task', _get_task)

    await hook.handle_github_app_terminal_task(
        TASK_ID, 'wrk-1', released_status='completed'
    )

    assert len(captured) == 1
    assert captured[0]['status'] == 'completed', (
        'the hook must signal the released status, not the stale read'
    )


@pytest.mark.asyncio
async def test_database_status_used_when_no_release_status_given(
    monkeypatch: pytest.MonkeyPatch, captured: list[dict]
) -> None:
    async def _get_task(_task_id):
        return _forgejo_task('completed')

    monkeypatch.setattr('a2a_server.database.db_get_task', _get_task)

    await hook.handle_github_app_terminal_task(TASK_ID, 'wrk-1')

    assert captured[0]['status'] == 'completed'


@pytest.mark.asyncio
async def test_failed_release_is_reported_as_failed(
    monkeypatch: pytest.MonkeyPatch, captured: list[dict]
) -> None:
    async def _get_task(_task_id):
        return _forgejo_task('running')

    monkeypatch.setattr('a2a_server.database.db_get_task', _get_task)

    await hook.handle_github_app_terminal_task(
        TASK_ID, 'wrk-1', released_status='failed'
    )

    assert captured[0]['status'] == 'failed'


@pytest.mark.asyncio
async def test_original_metadata_is_preserved(
    monkeypatch: pytest.MonkeyPatch, captured: list[dict]
) -> None:
    async def _get_task(_task_id):
        return _forgejo_task('running')

    monkeypatch.setattr('a2a_server.database.db_get_task', _get_task)

    await hook.handle_github_app_terminal_task(
        TASK_ID, 'wrk-1', released_status='completed'
    )

    metadata = captured[0]['metadata']
    assert metadata['forgejo_agent_task_id'] == 33
    assert metadata['workflow_stage'] == 'prepare'
    assert metadata['temporal_orchestrated'] is True


@pytest.mark.asyncio
async def test_missing_task_does_not_raise(
    monkeypatch: pytest.MonkeyPatch, captured: list[dict]
) -> None:
    async def _get_task(_task_id):
        return None

    monkeypatch.setattr('a2a_server.database.db_get_task', _get_task)

    await hook.handle_github_app_terminal_task(
        TASK_ID, 'wrk-1', released_status='completed'
    )

    assert captured == []
