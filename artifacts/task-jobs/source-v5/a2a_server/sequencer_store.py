"""Per-worker sequencer persistence for cross-connection SSE replay.

Holds one [`Sequencer`] (epoch + monotonic seq + replay ring) per worker_id so a
reconnecting worker keeps its epoch and can be replayed the gap it missed.
Survives individual SSE connections; bounded only by the number of distinct
workers. See codetether-agent/docs/transport-phase1-wire-contract.md section 5.
"""

from typing import Dict

from .replay_ring import ReplayRing
from .stream_emit import Sequencer
from .stream_epoch import mint_epoch


class SequencerStore:
    """Maps worker_id -> persistent Sequencer across reconnects."""

    def __init__(self) -> None:
        self._sequencers: Dict[str, Sequencer] = {}

    def get_or_create(self, worker_id: str) -> Sequencer:
        """Return the worker's existing sequencer, or mint a fresh one."""
        seq = self._sequencers.get(worker_id)
        if seq is None:
            seq = Sequencer(epoch=mint_epoch(), ring=ReplayRing())
            self._sequencers[worker_id] = seq
        return seq

    def drop(self, worker_id: str) -> None:
        """Forget a worker's sequencer (e.g. on permanent deregistration)."""
        self._sequencers.pop(worker_id, None)
