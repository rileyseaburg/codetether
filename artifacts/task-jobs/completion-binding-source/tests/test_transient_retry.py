"""Automatic requeue policy for transiently failed tasks.

Overloaded providers previously produced a terminal "failed" comment on the
Forgejo issue, so recovery required a human to mention @codetether again.
"""

from __future__ import annotations

import pytest

from a2a_server import transient_retry


@pytest.mark.parametrize(
    'error',
    [
        'Error: codex-retryable: Our servers are currently overloaded. Please try again later.',
        'stream error (503 Service Unavailable)',
        'Bad Gateway',
        'API error after 5 attempts: 429 Too Many Requests',
        'connection reset by peer',
        'codex-retryable: stream closed before response.completed',
        'idle timeout waiting for websocket',
    ],
)
def test_provider_faults_are_transient(error: str) -> None:
    assert transient_retry.is_transient_failure(error) is True
    assert transient_retry.is_permanent_failure(error) is False


@pytest.mark.parametrize(
    'error',
    [
        'Non-retryable provider error: 429 {"error":{"code":"1309","message":"package has expired"}}',
        'DeepSeek API error: Insufficient Balance',
        'OpenRouter API error: Insufficient credits',
        'stream error (402 Payment Required)',
        'Google Gemini API error: 403 PERMISSION_DENIED',
        'OpenAI Codex ChatGPT backend is disabled.',
        'Error: provider rejected prompt as too long after RLM compaction',
        'account has been suspended',
    ],
)
def test_permanent_conditions_are_never_requeued(error: str) -> None:
    assert transient_retry.is_permanent_failure(error) is True
    assert transient_retry.is_transient_failure(error) is False
    assert transient_retry.should_requeue('failed', error, {}) is False


def test_missing_error_is_not_transient() -> None:
    assert transient_retry.is_transient_failure(None) is False
    assert transient_retry.is_transient_failure('') is False


@pytest.mark.parametrize('status', ['completed', 'cancelled', 'running'])
def test_only_failed_releases_requeue(status: str) -> None:
    assert (
        transient_retry.should_requeue(status, 'currently overloaded', {})
        is False
    )


def test_retry_budget_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(
        'CODETETHER_TRANSIENT_RETRY_MAX_ATTEMPTS', raising=False
    )
    error = 'currently overloaded'

    assert transient_retry.max_attempts() == 3
    assert transient_retry.should_requeue('failed', error, {}) is True
    assert (
        transient_retry.should_requeue(
            'failed', error, {transient_retry.ATTEMPT_KEY: 2}
        )
        is True
    )
    assert (
        transient_retry.should_requeue(
            'failed', error, {transient_retry.ATTEMPT_KEY: 3}
        )
        is False
    )


def test_budget_is_configurable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('CODETETHER_TRANSIENT_RETRY_MAX_ATTEMPTS', '0')
    assert transient_retry.max_attempts() == 0
    assert (
        transient_retry.should_requeue('failed', 'currently overloaded', {})
        is False
    )

    monkeypatch.setenv('CODETETHER_TRANSIENT_RETRY_MAX_ATTEMPTS', 'garbage')
    assert transient_retry.max_attempts() == transient_retry.DEFAULT_MAX_ATTEMPTS


def test_metadata_advances_and_records_error() -> None:
    first = transient_retry.next_metadata({'repo': 'riley/x'}, 'overloaded')

    assert first[transient_retry.ATTEMPT_KEY] == 1
    assert first['repo'] == 'riley/x', 'existing metadata must be preserved'
    assert first[transient_retry.LAST_ERROR_KEY] == 'overloaded'

    second = transient_retry.next_metadata(first, 'overloaded again')
    assert second[transient_retry.ATTEMPT_KEY] == 2


def test_corrupt_attempt_counter_is_treated_as_zero() -> None:
    assert transient_retry.attempts_used({'transient_retry_attempts': 'x'}) == 0
    assert transient_retry.attempts_used({'transient_retry_attempts': -5}) == 0
    assert transient_retry.attempts_used(None) == 0


def test_backoff_grows_then_caps() -> None:
    assert transient_retry.backoff_seconds(1) == 30
    assert transient_retry.backoff_seconds(2) == 60
    assert transient_retry.backoff_seconds(3) == 120
    assert transient_retry.backoff_seconds(99) == 600


def test_long_errors_are_summarized() -> None:
    metadata = transient_retry.next_metadata({}, 'overloaded ' * 200)
    recorded = metadata[transient_retry.LAST_ERROR_KEY]

    assert len(recorded) <= 303
    assert recorded.endswith('...')
