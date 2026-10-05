"""Typed session events must survive the path from worker to Forgejo.

Tool activity previously reached the server as pre-joined text such as
`[tool:bash:ok] ...`, so `normalize_session_events` had no structure to classify
and every entry became `agent.message`. Forgejo's transcript only renders a tool
card for `tool.call` or `tool.result`, so 148 of 163 events on a live task were
tool activity that displayed as flat text.
"""

from __future__ import annotations

import pytest

from a2a_server.forgejo_agent_client import normalize_session_events


TASK = 'task-1'


def _types(messages: list[dict]) -> list[str]:
    return [event['type'] for event in normalize_session_events(TASK, messages)]


def test_declared_tool_call_is_published_as_tool_call() -> None:
    messages = [
        {
            'role': 'assistant',
            'content': '[tool:start:bash]',
            'tool_calls': [
                {
                    'codetether_event_type': 'tool.call',
                    'name': 'bash',
                    'status': 'started',
                    'arguments': {'command': 'ls'},
                }
            ],
        }
    ]

    assert _types(messages) == ['agent.message', 'tool.call']


def test_declared_tool_result_is_published_as_tool_result() -> None:
    messages = [
        {
            'role': 'assistant',
            'content': '[tool:bash:ok] done',
            'tool_calls': [
                {
                    'codetether_event_type': 'tool.result',
                    'name': 'bash',
                    'status': 'ok',
                    'success': True,
                    'output': 'done',
                }
            ],
        }
    ]

    assert _types(messages) == ['agent.message', 'tool.result']


def test_declared_type_beats_result_key_heuristic() -> None:
    """A started call that happens to carry an empty output is still a call."""
    messages = [
        {
            'role': 'assistant',
            'content': 'x',
            'tool_calls': [
                {
                    'codetether_event_type': 'tool.call',
                    'name': 'write',
                    'output': '',
                }
            ],
        }
    ]

    assert _types(messages)[1] == 'tool.call'


def test_marker_is_not_leaked_into_the_payload() -> None:
    messages = [
        {
            'role': 'assistant',
            'content': 'x',
            'tool_calls': [
                {'codetether_event_type': 'tool.result', 'name': 'read'}
            ],
        }
    ]

    events = normalize_session_events(TASK, messages)
    tool_event = events[1]

    assert 'codetether_event_type' not in tool_event['payload']
    assert tool_event['payload']['name'] == 'read'


def test_reasoning_role_becomes_reasoning_event() -> None:
    messages = [{'role': 'reasoning', 'content': 'Checking the test first.'}]

    assert _types(messages) == ['agent.reasoning']


def test_undeclared_records_keep_the_previous_heuristic() -> None:
    """Legacy rows written before typed events must still classify."""
    messages = [
        {
            'role': 'assistant',
            'content': 'x',
            'tool_calls': [
                {'name': 'bash', 'output': 'done'},
                {'name': 'bash'},
            ],
        }
    ]

    assert _types(messages) == ['agent.message', 'tool.result', 'tool.call']


def test_user_and_system_roles_are_unchanged() -> None:
    messages = [
        {'role': 'user', 'content': 'fix it'},
        {'role': 'system', 'content': 'policy'},
        {'role': 'assistant', 'content': 'ok'},
    ]

    assert _types(messages) == [
        'user.message',
        'system.message',
        'agent.message',
    ]


def test_sequence_numbers_stay_strictly_increasing() -> None:
    messages = [
        {
            'role': 'assistant',
            'content': 'a',
            'tool_calls': [
                {'codetether_event_type': 'tool.call', 'name': 'bash'},
                {'codetether_event_type': 'tool.result', 'name': 'bash'},
            ],
        },
        {'role': 'assistant', 'content': 'b'},
    ]

    sequences = [
        event['sequence'] for event in normalize_session_events(TASK, messages)
    ]

    assert sequences == sorted(sequences)
    assert len(set(sequences)) == len(sequences)


def test_external_ids_are_unique_per_event() -> None:
    messages = [
        {
            'role': 'assistant',
            'content': 'a',
            'tool_calls': [
                {'codetether_event_type': 'tool.call', 'name': 'bash'},
                {'codetether_event_type': 'tool.call', 'name': 'bash'},
            ],
        }
    ]

    ids = [
        event['external_id']
        for event in normalize_session_events(TASK, messages)
    ]

    assert len(set(ids)) == len(ids), (
        'duplicate ids would be skipped on publish'
    )


@pytest.mark.parametrize('bad', [None, 'text', 42, []])
def test_malformed_tool_records_are_skipped(bad: object) -> None:
    messages = [{'role': 'assistant', 'content': 'a', 'tool_calls': [bad]}]

    assert _types(messages) == ['agent.message']
