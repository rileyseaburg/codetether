"""Bounded per-stream replay ring for resumable worker SSE.

Application-layer analogue of the TCP retransmission queue: retains recent
sequenced (Class B) frames so a reconnecting client presenting a Last-Event-ID
can be replayed the gap. Bounded by min(N events, M bytes); oldest evicted
first. See codetether-agent/docs/transport-phase1-wire-contract.md section 4.
"""

from collections import deque
from dataclasses import dataclass
from typing import Deque, List, Optional


@dataclass
class RetainedFrame:
    """A sequenced frame retained for possible replay."""

    seq: int
    payload: str  # full SSE frame text, including trailing blank line


class ReplayRing:
    """Bounded ring of recent sequenced frames keyed by monotonic seq."""

    def __init__(self, max_events: int = 1024, max_bytes: int = 4 * 1024 * 1024):
        self._max_events = max_events
        self._max_bytes = max_bytes
        self._frames: Deque[RetainedFrame] = deque()
        self._bytes = 0

    def append(self, seq: int, payload: str) -> None:
        """Append a sequenced frame and evict until within both bounds."""
        self._frames.append(RetainedFrame(seq=seq, payload=payload))
        self._bytes += len(payload)
        while self._frames and (
            len(self._frames) > self._max_events or self._bytes > self._max_bytes
        ):
            evicted = self._frames.popleft()
            self._bytes -= len(evicted.payload)

    def lowest_retained_seq(self) -> Optional[int]:
        """Lowest seq still replayable, or None when the ring is empty."""
        return self._frames[0].seq if self._frames else None

    def replay_after(self, seq: int) -> List[str]:
        """Return payloads for all retained frames with seq strictly > `seq`."""
        return [f.payload for f in self._frames if f.seq > seq]
