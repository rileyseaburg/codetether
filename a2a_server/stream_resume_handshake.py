"""Connect-time resume handshake for the worker SSE stream.

Given a reconnecting client's Last-Event-ID and the worker's persistent
[`Sequencer`], yields the frames the client must receive before live events:
either a `resync-required` control event (epoch mismatch / window exceeded) or
the replayed gap `(seq, head]` from the ring. See
codetether-agent/docs/transport-phase1-wire-contract.md section 5.
"""

from typing import Iterator, Optional

from .stream_emit import Sequencer, format_event
from .stream_epoch import ResumeAction, decide_resume

_REASON = {
    ResumeAction.RESYNC_EPOCH: 'epoch_mismatch',
    ResumeAction.RESYNC_WINDOW: 'window_exceeded',
}


def resume_frames(last_event_id: Optional[str], seq: Sequencer) -> Iterator[str]:
    """Yield resync or replayed frames for a reconnecting client."""
    decision = decide_resume(
        last_event_id, seq.epoch, seq.ring.lowest_retained_seq()
    )
    if decision.action in _REASON:
        head = seq.next_seq - 1
        event = {
            'reason': _REASON[decision.action],
            'head_seq': head,
            'epoch': seq.epoch,
        }
        yield format_event('resync-required', event, seq)
    elif decision.action == ResumeAction.REPLAY and decision.after_seq is not None:
        for payload in seq.ring.replay_after(decision.after_seq):
            yield payload
