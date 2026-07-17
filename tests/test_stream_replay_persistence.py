"""Tests for cross-connection replay: SequencerStore + resume handshake."""

from a2a_server.sequencer_store import SequencerStore
from a2a_server.stream_emit import format_event
from a2a_server.stream_resume_handshake import resume_frames


def test_store_persists_epoch_across_lookups():
    store = SequencerStore()
    first = store.get_or_create("w1")
    again = store.get_or_create("w1")
    assert first is again
    assert first.epoch == again.epoch


def test_store_distinct_workers_get_distinct_sequencers():
    store = SequencerStore()
    assert store.get_or_create("w1") is not store.get_or_create("w2")


def test_first_connect_yields_no_frames():
    store = SequencerStore()
    seq = store.get_or_create("w1")
    assert list(resume_frames(None, seq)) == []


def test_reconnect_replays_gap_within_window():
    store = SequencerStore()
    seq = store.get_or_create("w1")
    # connection 1 emits three sequenced events
    for pct in (10, 20, 30):
        format_event('progress', {'pct': pct}, seq)
    # client processed up to seq 1, reconnects with same worker_id
    seq2 = store.get_or_create("w1")
    assert seq2 is seq
    frames = list(resume_frames(f"{seq.epoch}.1", seq2))
    assert len(frames) == 2
    assert f"id: {seq.epoch}.2\n" in frames[0]
    assert f"id: {seq.epoch}.3\n" in frames[1]


def test_reconnect_foreign_epoch_emits_resync():
    store = SequencerStore()
    seq = store.get_or_create("w1")
    format_event('progress', {'pct': 10}, seq)
    frames = list(resume_frames("oldepoch.1", seq))
    assert len(frames) == 1
    assert "event: resync-required" in frames[0]
    assert "epoch_mismatch" in frames[0]


def test_reconnect_window_exceeded_emits_resync():
    store = SequencerStore()
    seq = store.get_or_create("w1")
    # shrink the window so seq 1 is evicted
    seq.ring._max_events = 2
    for pct in (10, 20, 30, 40):
        format_event('progress', {'pct': pct}, seq)
    frames = list(resume_frames(f"{seq.epoch}.1", seq))
    assert len(frames) == 1
    assert "window_exceeded" in frames[0]
