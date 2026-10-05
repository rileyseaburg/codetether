"""Automatic requeue of tasks that failed for transient provider reasons.

A provider that is briefly overloaded, rate-limited, or dropped a stream is not
a defect in the task: retrying the same work later usually succeeds. Before
this module, such failures were terminal, so a Forgejo `@codetether` mention
produced a "failed" comment and a human had to mention the bot again.

Permanent conditions (expired plan, insufficient balance, suspended account,
prompt genuinely too long) are never requeued: no amount of retrying clears
them, and silent retry loops waste worker slots.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Metadata keys used to bound automatic retries per task.
ATTEMPT_KEY = 'transient_retry_attempts'
LAST_ERROR_KEY = 'transient_retry_last_error'

# Metadata key the worker reads to continue an existing agent session rather
# than starting over. Equivalent to `codetether run --session <id>`.
RESUME_KEY = 'resume_session_id'

DEFAULT_MAX_ATTEMPTS = 3

# Substrings that indicate the provider (not the work) failed, and that the
# same task is likely to succeed on a later attempt.
_TRANSIENT_PATTERNS: Tuple[str, ...] = (
    'codex-retryable',
    'currently overloaded',
    'temporarily overloaded',
    'server_error',
    'service unavailable',
    'bad gateway',
    'gateway timeout',
    'too many requests',
    'rate limit',
    'timed out',
    'timeout waiting',
    'connection reset',
    'connection closed',
    # A truncated or malformed streaming response is a transport fault, not a
    # defective task: the same work usually succeeds on a later attempt.
    'sse stream error',
    'error decoding response body',
    'incomplete message',
    'unexpected eof',
    'stream closed before',
    'stream disconnected',
    'internal server error',
    'please try again',
)

# Substrings that must never be auto-requeued even if they also look transient
# (for example, a 429 whose body reports an expired subscription).
_PERMANENT_PATTERNS: Tuple[str, ...] = (
    'has expired',
    'package has expired',
    'subscription has expired',
    'renewing the subscription',
    'renew the subscription',
    'insufficient balance',
    'insufficient credits',
    'payment required',
    'account has been suspended',
    'account is locked',
    'permission_denied',
    'invalid api key',
    'unauthorized',
    'backend is disabled',
    'too long after rlm compaction',
    'prompt as too long',
    '"1309"',
    'code":1309',
)


def max_attempts() -> int:
    """Return the bound on automatic requeues for one task."""
    raw = os.environ.get('CODETETHER_TRANSIENT_RETRY_MAX_ATTEMPTS', '')
    try:
        parsed = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_MAX_ATTEMPTS
    return parsed if parsed >= 0 else DEFAULT_MAX_ATTEMPTS


def is_permanent_failure(error: Optional[str]) -> bool:
    """Return true when `error` describes a condition retrying cannot clear."""
    lowered = (error or '').lower()
    return any(pattern in lowered for pattern in _PERMANENT_PATTERNS)


def is_transient_failure(error: Optional[str]) -> bool:
    """Return true when `error` looks like a retryable provider fault.

    Permanent conditions win over transient ones so a rate-limit response that
    really reports an expired plan is not requeued forever.
    """
    if not error:
        return False
    if is_permanent_failure(error):
        return False
    lowered = error.lower()
    return any(pattern in lowered for pattern in _TRANSIENT_PATTERNS)


def attempts_used(metadata: Optional[Dict[str, Any]]) -> int:
    """Return how many automatic requeues this task has already consumed."""
    if not metadata:
        return 0
    raw = metadata.get(ATTEMPT_KEY)
    try:
        used = int(raw)
    except (TypeError, ValueError):
        return 0
    return max(used, 0)


def should_requeue(
    status: str,
    error: Optional[str],
    metadata: Optional[Dict[str, Any]],
) -> bool:
    """Decide whether a released task should return to the pending queue."""
    if status != 'failed':
        return False
    if not is_transient_failure(error):
        return False
    return attempts_used(metadata) < max_attempts()


def backoff_seconds(attempt: int) -> int:
    """Return the delay before a requeued attempt becomes eligible again.

    Produces 30s, 60s, 120s, ... capped at 600s so a provider outage does not
    become a hot retry loop.
    """
    exponent = max(attempt, 1) - 1
    return min(30 * (2**exponent), 600)


def next_metadata(
    metadata: Optional[Dict[str, Any]],
    error: Optional[str],
) -> Dict[str, Any]:
    """Return task metadata with the retry counter advanced and resume set.

    A transient fault can occur many minutes into a long task. Requeuing without
    a resume pointer threw that work away and restarted from the prompt, so a
    stream that broke near the end simply burned the retry budget. Carrying the
    established session forward makes the next attempt continue where it stopped,
    the same way `codetether run --session <id>` does.
    """
    updated = dict(metadata or {})
    updated[ATTEMPT_KEY] = attempts_used(metadata) + 1
    if error:
        updated[LAST_ERROR_KEY] = _summarize(error)
    resume = resume_target(metadata)
    if resume:
        updated[RESUME_KEY] = resume
    return updated


def resume_target(metadata: Optional[Dict[str, Any]]) -> Optional[str]:
    """Return the session a retry should continue, if one is known.

    Prefers an explicit resume pointer, then the worker's own reported session,
    then the session the transcript was recorded under. Derived `task-<id>`
    sessions hold streamed narration rather than agent state, so they are only
    used when nothing better exists.
    """
    data = metadata or {}
    for key in (RESUME_KEY, 'worker_session_id', 'session_id'):
        value = str(data.get(key) or '').strip()
        if value and not value.startswith('task-'):
            return value
    return None


def _summarize(error: str, limit: int = 300) -> str:
    collapsed = re.sub(r'\s+', ' ', error).strip()
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[:limit] + '...'