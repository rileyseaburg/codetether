"""Tests for cross-connection replay: SequencerStore + resume_frames."""

from a2a_server.sequencer_store import SequencerStore
from a2a_server.stream_emit import format_event
from a2a_server.stream_resume_handshake import resume_frames


def test_store_persists_epoch_across_reconnects():
    store = SequencerStore()
    first = store.get_or_create('w1')
    first_epoch = first.epoch
    format_event('progress', {'pct': 10}, first)
    # Simulate reconnect: same worker_id returns the same sequencer/epoch.
    again = store.get_or_create('w1')
    assert again is first
    assert again.epoch == first_epoch
    assert again.next_seq == 2


def test_store_distinct_workers_get_distinct_sequencers():
    store = SequencerStore()
    assert store.get_or_create('a') is not store.get_or_create('b')


def test_store_drop_forgets_worker():
    store = SequencerStore()
    s1 = store.get_or_create('w1')
    store.drop('w1')
    assert store.get_or_create('w1') is not s1


def test_resume_frames_replays_gap_within_window():
    store = SequencerStore()
    seq = store.get_or_create('w1')
    for pct in (10, 20, 30):
        format_event('progress', {'pct': pct}, seq)
    # Client processed up to seq 1; reconnect replays seq 2 and 3.
    last_id = f'{seq.epoch}.1'
    frames = list(resume_frames(last_id, seq))
    assert len(frames) == 2
    assert f'id: {seq.epoch}.2\n' in frames[0]
    assert f'id: {seq.epoch}.3\n' in frames[1]


def test_resume_frames_epoch_mismatch_emits_resync():
    store = SequencerStore()
    seq = store.get_or_create('w1')
    format_event('progress', {'pct': 10}, seq)
    frames = list(resume_frames('foreign.1', seq))
    assert len(frames) == 1
    assert 'event: resync-required' in frames[0]
    assert 'epoch_mismatch' in frames[0]


def test_resume_frames_window_exceeded_emits_resync():
    store = SequencerStore()
    seq = store.get_or_create('w1')
    # Shrink the ring so early seqs are evicted past the client's cursor.
    seq.ring._max_events = 1
    for pct in (10, 20, 30):
        format_event('progress', {'pct': pct}, seq)
    frames = list(resume_frames(f'{seq.epoch}.1', seq))
    assert len(frames) == 1
    assert 'window_exceeded' in frames[0]


def test_resume_frames_first_connect_yields_nothing():
    store = SequencerStore()
    seq = store.get_or_create('w1')
    assert list(resume_frames(None, seq)) == []
