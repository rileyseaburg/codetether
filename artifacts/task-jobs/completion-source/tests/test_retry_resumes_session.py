"""A retried task must resume its session, not restart from the prompt.

A transient fault can land many minutes into a long task. Requeuing without a
resume pointer discarded that work and began again from the original prompt, so a
stream that broke near the end simply burned the retry budget. The worker already
honours `resume_session_id` (the metadata equivalent of `codetether run
--session <id>`), so the requeue must carry it forward.
"""

from __future__ import annotations

import pytest

from a2a_server import transient_retry

ERROR = 'Error: SSE stream error: error decoding response body'


def test_worker_session_is_carried_into_the_retry() -> None:
    metadata = {'worker_session_id': 'sess-real-1'}

    updated = transient_retry.next_metadata(metadata, ERROR)

    assert updated[transient_retry.RESUME_KEY] == 'sess-real-1'
    assert updated[transient_retry.ATTEMPT_KEY] == 1


def test_existing_resume_pointer_is_preserved() -> None:
    metadata = {
        transient_retry.RESUME_KEY: 'sess-first',
        'worker_session_id': 'sess-second',
    }

    updated = transient_retry.next_metadata(metadata, ERROR)

    assert updated[transient_retry.RESUME_KEY] == 'sess-first', (
        'an explicit resume pointer wins over a later reported session'
    )


def test_plain_session_id_is_usable() -> None:
    metadata = {'session_id': 'sess-plain'}

    assert transient_retry.resume_target(metadata) == 'sess-plain'


def test_derived_task_session_is_not_a_resume_target() -> None:
    """`task-<id>` sessions hold streamed narration, not agent state."""
    metadata = {'session_id': 'task-abc-123'}

    assert transient_retry.resume_target(metadata) is None

    updated = transient_retry.next_metadata(metadata, ERROR)
    assert transient_retry.RESUME_KEY not in updated


def test_derived_session_yields_to_a_real_one() -> None:
    metadata = {
        'session_id': 'task-abc-123',
        'worker_session_id': 'sess-real-2',
    }

    assert transient_retry.resume_target(metadata) == 'sess-real-2'


def test_no_session_means_no_resume_key() -> None:
    updated = transient_retry.next_metadata({'repo': 'riley/x'}, ERROR)

    assert transient_retry.RESUME_KEY not in updated
    assert updated['repo'] == 'riley/x'


def test_blank_values_are_ignored() -> None:
    assert transient_retry.resume_target({'session_id': '   '}) is None
    assert transient_retry.resume_target({'worker_session_id': ''}) is None
    assert transient_retry.resume_target(None) is None


def test_resume_survives_repeated_attempts() -> None:
    metadata = {'worker_session_id': 'sess-keep'}

    first = transient_retry.next_metadata(metadata, ERROR)
    second = transient_retry.next_metadata(first, ERROR)

    assert second[transient_retry.RESUME_KEY] == 'sess-keep'
    assert second[transient_retry.ATTEMPT_KEY] == 2


def test_streaming_fault_still_requeues_with_resume() -> None:
    metadata = {'worker_session_id': 'sess-keep'}

    assert transient_retry.should_requeue('failed', ERROR, metadata) is True
    updated = transient_retry.next_metadata(metadata, ERROR)
    assert updated[transient_retry.RESUME_KEY] == 'sess-keep'
