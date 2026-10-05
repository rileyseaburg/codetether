"""Stream epoch minting and Last-Event-ID resume decision logic.

An epoch is an opaque token minted per logical stream lifetime; it guards
against seq reuse across server restarts (a client presenting an id from a
different epoch must cold-resync). See
codetether-agent/docs/transport-phase1-wire-contract.md section 5.
"""

import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Optional


def mint_epoch() -> str:
    """Mint a fresh opaque epoch token for a new stream lifetime."""
    return uuid.uuid4().hex[:12]


def parse_last_event_id(raw: Optional[str]) -> Optional[tuple[str, int]]:
    """Parse a `Last-Event-ID` of the form `<epoch>.<seq>`.

    Returns (epoch, seq) when well-formed, else None.
    """
    if not raw:
        return None
    epoch, _, seq = raw.rpartition('.')
    if not epoch:
        return None
    try:
        return (epoch, int(seq))
    except ValueError:
        return None


class ResumeAction(str, Enum):
    """What the server should do for a presented Last-Event-ID."""

    COLD = 'cold'  # no/invalid id: start live with no replay
    REPLAY = 'replay'  # replay (seq, head] then live
    RESYNC_EPOCH = 'resync_epoch'  # epoch mismatch
    RESYNC_WINDOW = 'resync_window'  # fell out of replay window


@dataclass
class ResumeDecision:
    """Decision plus the seq to replay after (for REPLAY)."""

    action: ResumeAction
    after_seq: Optional[int] = None


def decide_resume(
    raw_last_event_id: Optional[str],
    current_epoch: str,
    lowest_retained_seq: Optional[int],
) -> ResumeDecision:
    """Apply the section 5 decision table for a reconnecting client."""
    parsed = parse_last_event_id(raw_last_event_id)
    if parsed is None:
        return ResumeDecision(ResumeAction.COLD)
    epoch, seq = parsed
    if epoch != current_epoch:
        return ResumeDecision(ResumeAction.RESYNC_EPOCH)
    if lowest_retained_seq is None or seq < lowest_retained_seq - 1:
        return ResumeDecision(ResumeAction.RESYNC_WINDOW)
    return ResumeDecision(ResumeAction.REPLAY, after_seq=seq)
