"""Tests for replay_ring and stream_epoch resume logic."""

from a2a_server.replay_ring import ReplayRing
from a2a_server.stream_epoch import (
    ResumeAction,
    decide_resume,
    mint_epoch,
    parse_last_event_id,
)
from a2a_server.stream_emit import Sequencer, format_event, is_sequenced


def test_ring_evicts_by_count():
    ring = ReplayRing(max_events=3, max_bytes=10_000)
    for seq in range(1, 6):
        ring.append(seq, f"id: e.{seq}\n\n")
    assert ring.lowest_retained_seq() == 3
    assert ring.replay_after(3) == ["id: e.4\n\n", "id: e.5\n\n"]


def test_ring_evicts_by_bytes():
    ring = ReplayRing(max_events=1000, max_bytes=20)
    ring.append(1, "x" * 15)
    ring.append(2, "y" * 15)
    assert ring.lowest_retained_seq() == 2


def test_parse_last_event_id():
    assert parse_last_event_id("ep.42") == ("ep", 42)
    assert parse_last_event_id("a.b.7") == ("a.b", 7)
    assert parse_last_event_id(None) is None
    assert parse_last_event_id(".5") is None
    assert parse_last_event_id("ep.x") is None


def test_decide_cold_when_no_id():
    assert decide_resume(None, "ep", 1).action == ResumeAction.COLD


def test_decide_epoch_mismatch():
    assert decide_resume("other.5", "ep", 1).action == ResumeAction.RESYNC_EPOCH


def test_decide_replay_within_window():
    d = decide_resume("ep.5", "ep", 3)
    assert d.action == ResumeAction.REPLAY
    assert d.after_seq == 5


def test_decide_resync_window_exceeded():
    assert decide_resume("ep.1", "ep", 10).action == ResumeAction.RESYNC_WINDOW


def test_decide_boundary_is_replay():
    # last-processed exactly one below lowest retained: still replayable
    assert decide_resume("ep.4", "ep", 5).action == ResumeAction.REPLAY


def test_mint_epoch_unique():
    assert mint_epoch() != mint_epoch()


# --- integration: emission + ring + decision together ---


def _seq():
    return Sequencer(
        epoch=mint_epoch(), ring=ReplayRing(max_events=100, max_bytes=10_000)
    )


def test_sequenced_events_get_ids_advisory_do_not():
    s = _seq()
    advisory = format_event('task_available', {'id': 't1'}, s)
    sequenced = format_event('progress', {'pct': 50}, s)
    assert 'id: ' not in advisory
    assert sequenced.startswith(f'id: {s.epoch}.1\n')
    assert s.next_seq == 2


def test_live_replay_after_returns_only_later_seqs():
    s = _seq()
    for pct in (10, 20, 30):
        format_event('progress', {'pct': pct}, s)
    payloads = s.ring.replay_after(1)
    assert len(payloads) == 2
    assert f'id: {s.epoch}.2\n' in payloads[0]
    assert f'id: {s.epoch}.3\n' in payloads[1]


def test_reconnect_with_foreign_epoch_decides_resync():
    s = _seq()
    format_event('progress', {'pct': 10}, s)
    decision = decide_resume('oldepoch.1', s.epoch, s.ring.lowest_retained_seq())
    assert decision.action == ResumeAction.RESYNC_EPOCH


def test_control_and_heartbeat_are_unsequenced():
    assert not is_sequenced('connected')
    assert not is_sequenced('heartbeat')
    assert not is_sequenced('resync-required')
    assert is_sequenced('progress')
    assert is_sequenced('result')
