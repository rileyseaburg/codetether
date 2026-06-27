"""SSE frame emission with optional resumable id assignment.

Classifies an event server-side and, for sequenced (Class B) events, assigns a
monotonic `id: <epoch>.<seq>`, records the frame in the replay ring, and returns
the wire text. Advisory/control events are emitted without an id. See
codetether-agent/docs/transport-phase1-wire-contract.md sections 2-4.
"""

import json
from dataclasses import dataclass
from typing import Any, Dict

from .replay_ring import ReplayRing

# Event types that are NOT sequenced: advisory (claim-gated) + control/liveness.
_UNSEQUENCED = {'connected', 'heartbeat', 'task_available', 'resync-required'}


@dataclass
class Sequencer:
    """Per-connection sequencing state."""

    epoch: str
    ring: ReplayRing
    next_seq: int = 1


def is_sequenced(event_type: str) -> bool:
    """True when the event type carries an id and lives in the replay ring."""
    return event_type not in _UNSEQUENCED


def format_event(event_type: str, data: Dict[str, Any], seq: Sequencer) -> str:
    """Format an SSE frame, assigning an id and recording it when sequenced."""
    body = f'event: {event_type}\ndata: {json.dumps(data)}\n\n'
    if not is_sequenced(event_type):
        return body
    framed = f'id: {seq.epoch}.{seq.next_seq}\n{body}'
    seq.ring.append(seq.next_seq, framed)
    seq.next_seq += 1
    return framed
