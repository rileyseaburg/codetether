"""Mocked-local SSE producer contracts; no live DB, workers, or HTTP auth."""

import json
import os
from unittest.mock import AsyncMock, call

import pytest
from fastapi import HTTPException
from starlette.requests import Request

os.environ.setdefault('DATABASE_URL', 'postgresql://localhost/task_output_test')

from a2a_server import monitor_api, task_output


def request_for(last_event_id=None):
    headers = []
    if last_event_id is not None:
        headers.append((b'last-event-id', last_event_id.encode()))
    request = Request({'type': 'http', 'headers': headers})
    request.is_disconnected = AsyncMock(return_value=False)
    return request


def page(status, cursors=(), *, has_more=False, next_cursor=None):
    outputs = [
        {'task_id': 'task-a', 'cursor': cursor, 'output': f'chunk-{cursor}'}
        for cursor in cursors
    ]
    return {
        'task_id': 'task-a', 'status': status, 'outputs': outputs,
        'has_more': has_more,
        'next_cursor': next_cursor if next_cursor is not None else (
            outputs[-1]['cursor'] if outputs else 0
        ),
    }


@pytest.mark.asyncio
@pytest.mark.parametrize('status', ['completed', 'failed', 'cancelled'])
async def test_terminal_stream_drains_all_pages_before_done(monkeypatch, status):
    request = request_for()
    read = AsyncMock(side_effect=[
        page(status, range(1, 1001), has_more=True),
        page(status, [1001]),
    ])
    monkeypatch.setattr(task_output, 'read_output', read)

    response = await monitor_api.stream_task_output_sse('task-a', request)
    # Preflight authorizes through read_output before response headers are sent.
    read.assert_awaited_once_with(request, 'task-a', 0)
    events = [event async for event in response.body_iterator]

    assert [event['event'] for event in events] == ['output'] * 1001 + ['done']
    assert [event['id'] for event in events[:-1]] == [
        str(cursor) for cursor in range(1, 1002)
    ]
    assert json.loads(events[-1]['data']) == {
        'task_id': 'task-a', 'status': status, 'next_cursor': 1001,
    }
    assert read.await_args_list == [
        call(request, 'task-a', 0), call(request, 'task-a', 1000),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize('status', ['completed', 'failed', 'cancelled'])
async def test_follow_polls_then_drains_output_before_terminal(monkeypatch, status):
    request = request_for('7')
    read = AsyncMock(side_effect=[
        page('running', next_cursor=7),
        page('running', [8], has_more=True),
        page(status, [9]),
    ])
    monkeypatch.setattr(task_output, 'read_output', read)
    sleep = AsyncMock()
    monkeypatch.setattr(monitor_api.asyncio, 'sleep', sleep)

    response = await monitor_api.stream_task_output_sse('task-a', request)
    events = [event async for event in response.body_iterator]

    assert [event['event'] for event in events] == ['output', 'output', 'done']
    assert [event['id'] for event in events[:-1]] == ['8', '9']
    assert json.loads(events[-1]['data']) == {
        'task_id': 'task-a', 'status': status, 'next_cursor': 9,
    }
    assert read.await_args_list == [
        call(request, 'task-a', 7), call(request, 'task-a', 7),
        call(request, 'task-a', 8),
    ]
    sleep.assert_awaited_once_with(0.1)


@pytest.mark.asyncio
async def test_reconnect_reauthorizes_instead_of_reusing_terminal_page(monkeypatch):
    read = AsyncMock(side_effect=[
        page('completed', [1]), HTTPException(403, 'output forbidden'),
    ])
    monkeypatch.setattr(task_output, 'read_output', read)
    first_request = request_for()
    response = await monitor_api.stream_task_output_sse('task-a', first_request)
    assert [event['event'] async for event in response.body_iterator] == [
        'output', 'done',
    ]

    reconnect = request_for('1')
    with pytest.raises(HTTPException) as error:
        await monitor_api.stream_task_output_sse('task-a', reconnect)
    assert error.value.status_code == 403
    assert read.await_args_list == [
        call(first_request, 'task-a', 0), call(reconnect, 'task-a', 1),
    ]


@pytest.mark.asyncio
async def test_last_event_id_wins_and_empty_terminal_page_retains_cursor(monkeypatch):
    request = request_for('9')
    read = AsyncMock(return_value=page('completed', next_cursor=9))
    monkeypatch.setattr(task_output, 'read_output', read)

    response = await monitor_api.stream_task_output_sse('task-a', request, since=2)
    events = [event async for event in response.body_iterator]

    read.assert_awaited_once_with(request, 'task-a', 9)
    assert len(events) == 1
    assert events[0]['event'] == 'done'
    assert json.loads(events[0]['data'])['next_cursor'] == 9


@pytest.mark.asyncio
@pytest.mark.parametrize('code', [403, 404, 503])
async def test_preflight_failure_does_not_send_success_response(monkeypatch, code):
    read = AsyncMock(side_effect=HTTPException(code, 'output unavailable'))
    monkeypatch.setattr(task_output, 'read_output', read)

    with pytest.raises(HTTPException) as error:
        await monitor_api.stream_task_output_sse('task-a', request_for())
    assert error.value.status_code == code


@pytest.mark.asyncio
async def test_malformed_last_event_id_is_rejected_before_storage(monkeypatch):
    read = AsyncMock()
    monkeypatch.setattr(task_output, 'read_output', read)

    with pytest.raises(HTTPException) as error:
        await monitor_api.stream_task_output_sse('task-a', request_for('not-a-cursor'))
    assert error.value.status_code == 422
    read.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('code', [403, 503])
async def test_follow_read_failure_closes_without_false_completion(monkeypatch, code):
    request = request_for()
    read = AsyncMock(side_effect=[
        page('running', [1]), HTTPException(code, 'output unavailable'),
    ])
    monkeypatch.setattr(task_output, 'read_output', read)
    # Don't wait for poll delay; storage and authorization are mocked local.
    monkeypatch.setattr(monitor_api.asyncio, 'sleep', AsyncMock())

    response = await monitor_api.stream_task_output_sse('task-a', request)
    events = [event async for event in response.body_iterator]

    assert [event['event'] for event in events] == ['output']
    assert read.await_args_list == [
        call(request, 'task-a', 0), call(request, 'task-a', 1),
    ]


@pytest.mark.asyncio
async def test_disconnect_stops_replay_without_done(monkeypatch):
    request = request_for()
    request.is_disconnected.return_value = True
    read = AsyncMock(return_value=page('completed', [1]))
    monkeypatch.setattr(task_output, 'read_output', read)

    response = await monitor_api.stream_task_output_sse('task-a', request)

    assert [event async for event in response.body_iterator] == []
    read.assert_awaited_once_with(request, 'task-a', 0)