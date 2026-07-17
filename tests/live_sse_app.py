"""Minimal live SSE app exercising the real resume machinery.

Mounts the production resume modules (Sequencer, ReplayRing, resume_frames,
format_event) over a real socket so the resumable-stream contract can be proven
end-to-end with an actual TCP connection that gets killed mid-stream. This is a
thin test harness app, not a production endpoint — it deliberately strips auth,
DB, and the worker registry to isolate the transport/resume behavior.
"""

import asyncio

from fastapi import FastAPI, Header, Request
from fastapi.responses import StreamingResponse

from a2a_server.replay_ring import ReplayRing
from a2a_server.sequencer_store import SequencerStore
from a2a_server.stream_emit import Sequencer, format_event
from a2a_server.stream_epoch import mint_epoch
from a2a_server.stream_resume_handshake import resume_frames

app = FastAPI()
_store = SequencerStore()
# Sequencers with a deliberately tiny ring to force window-exceeded behavior.
_tiny_store: dict[str, Sequencer] = {}
# Total sequenced events the server will emit per logical stream lifetime.
_TOTAL = 100


@app.post('/_reset')
async def reset():
    """Drop all sequencer state, simulating a server restart (new epochs)."""
    global _store, _tiny_store
    _store = SequencerStore()
    _tiny_store = {}
    return {'ok': True}


def _stream_response(seq: Sequencer, last_event_id: str | None, total: int):
    async def gen():
        for frame in resume_frames(last_event_id, seq):
            yield frame
        while seq.next_seq <= total:
            yield format_event('progress', {'n': seq.next_seq}, seq)
            await asyncio.sleep(0.01)

    return StreamingResponse(gen(), media_type='text/event-stream')


@app.get('/stream')
async def stream(request: Request, last_event_id: str | None = Header(None)):
    """Emit sequenced `progress` events 1.._TOTAL, resuming via Last-Event-ID."""
    worker_id = request.query_params.get('worker_id', 'w1')
    return _stream_response(
        _store.get_or_create(worker_id), last_event_id, _TOTAL
    )


@app.get('/stream_tiny')
async def stream_tiny(request: Request, last_event_id: str | None = Header(None)):
    """Stream backed by a 2-event ring so early seqs are quickly evicted."""
    worker_id = request.query_params.get('worker_id', 'tiny')
    seq = _tiny_store.get(worker_id)
    if seq is None:
        seq = Sequencer(epoch=mint_epoch(), ring=ReplayRing(max_events=2))
        _tiny_store[worker_id] = seq
    return _stream_response(seq, last_event_id, _TOTAL)


@app.get('/stream_advisory')
async def stream_advisory(request: Request):
    """Emit one advisory (task_available) then sequenced events.

    Advisory frames must carry no `id:` and must not consume a sequence number.
    """
    worker_id = request.query_params.get('worker_id', 'adv')
    seq = _store.get_or_create(worker_id)

    async def gen():
        yield format_event('task_available', {'id': 'task-1'}, seq)
        for _ in range(3):
            yield format_event('progress', {'n': seq.next_seq}, seq)
            await asyncio.sleep(0.01)

    return StreamingResponse(gen(), media_type='text/event-stream')
