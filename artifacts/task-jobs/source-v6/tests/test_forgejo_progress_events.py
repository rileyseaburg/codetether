"""In-flight Forgejo transcript publishing.

The Forgejo task page's "Session transcript" panel was empty for the whole life
of a run because events were only published by the terminal-task hook.
"""

from __future__ import annotations

import pytest

from a2a_server import forgejo_progress_events as progress


@pytest.fixture(autouse=True)
def _clean_state(monkeypatch: pytest.MonkeyPatch):
    progress.reset()
    monkeypatch.delenv('CODETETHER_FORGEJO_PROGRESS_EVENTS', raising=False)
    monkeypatch.delenv(
        'CODETETHER_FORGEJO_PROGRESS_INTERVAL_SECONDS', raising=False
    )
    yield
    progress.reset()


def test_enabled_by_default() -> None:
    assert progress.progress_publishing_enabled() is True
    assert progress.min_interval_seconds() == 20.0


def test_can_be_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('CODETETHER_FORGEJO_PROGRESS_EVENTS', 'false')
    assert progress.progress_publishing_enabled() is False


def test_invalid_interval_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        'CODETETHER_FORGEJO_PROGRESS_INTERVAL_SECONDS', 'not-a-number'
    )
    assert progress.min_interval_seconds() == 20.0

    monkeypatch.setenv('CODETETHER_FORGEJO_PROGRESS_INTERVAL_SECONDS', '-5')
    assert progress.min_interval_seconds() == 20.0


def test_first_publish_allowed_then_throttled() -> None:
    assert progress.should_publish('task-a', now=1000.0) is True
    assert progress.should_publish('task-a', now=1005.0) is False
    assert progress.should_publish('task-a', now=1019.9) is False
    assert progress.should_publish('task-a', now=1020.1) is True


def test_throttle_is_per_task() -> None:
    assert progress.should_publish('task-a', now=500.0) is True
    assert progress.should_publish('task-b', now=500.0) is True, (
        'one chatty task must not throttle another'
    )


def test_forget_allows_immediate_republish() -> None:
    assert progress.should_publish('task-a', now=10.0) is True
    assert progress.should_publish('task-a', now=11.0) is False

    progress.forget('task-a')

    assert progress.should_publish('task-a', now=11.5) is True


def test_empty_task_id_never_publishes() -> None:
    assert progress.should_publish('', now=1.0) is False


def test_throttle_map_is_bounded() -> None:
    for index in range(progress._MAX_TRACKED_TASKS + 10):
        progress.should_publish(f'task-{index}', now=float(index))

    assert len(progress._LAST_PUBLISH) <= progress._MAX_TRACKED_TASKS


@pytest.mark.parametrize(
    'metadata,expected',
    [
        ({'source': 'forgejo-webhook', 'forgejo_agent_task_id': 15}, True),
        ({'source': 'forgejo-webhook', 'forgejo_agent_task_id': '15'}, True),
        ({'source': 'forgejo-webhook', 'forgejo_agent_task_id': 0}, False),
        ({'source': 'forgejo-webhook'}, False),
        ({'source': 'github-app', 'forgejo_agent_task_id': 15}, False),
        ({}, False),
    ],
)
def test_only_native_forgejo_tasks_qualify(
    metadata: dict, expected: bool
) -> None:
    assert progress.is_forgejo_agent_task({'metadata': metadata}) is expected


def test_missing_task_is_not_forgejo() -> None:
    assert progress.is_forgejo_agent_task(None) is False
    assert progress.is_forgejo_agent_task({}) is False


def test_corrupt_task_id_is_not_forgejo() -> None:
    task = {
        'metadata': {
            'source': 'forgejo-webhook',
            'forgejo_agent_task_id': 'not-an-int',
        }
    }
    assert progress.is_forgejo_agent_task(task) is False


@pytest.mark.asyncio
async def test_disabled_publisher_does_no_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv('CODETETHER_FORGEJO_PROGRESS_EVENTS', 'off')

    def _explode(*args, **kwargs):  # pragma: no cover - must not be called
        raise AssertionError('publisher must not touch the database')

    monkeypatch.setattr(
        'a2a_server.database.db_get_task', _explode, raising=False
    )

    assert await progress.publish_task_progress('task-a') == 0


@pytest.mark.asyncio
async def test_terminal_task_defers_to_terminal_hook(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _task(task_id: str):
        return {
            'id': task_id,
            'status': 'completed',
            'metadata': {
                'source': 'forgejo-webhook',
                'forgejo_agent_task_id': 15,
                'repo': 'riley/spotlessbinco',
            },
        }

    monkeypatch.setattr('a2a_server.database.db_get_task', _task)

    assert await progress.publish_task_progress('task-a') == 0
    assert 'task-a' not in progress._LAST_PUBLISH, (
        'terminal tasks must release throttle state'
    )
