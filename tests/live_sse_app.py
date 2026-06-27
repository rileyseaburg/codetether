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

from a2a_server.sequencer_store import SequencerStore
from a2a_server.stream_emit import format_event
from a2a_server.stream_resume_handshake import resume_frames

app = FastAPI()
_store = SequencerStore()
# Total sequenced events the server will emit per logical stream lifetime.
_TOTAL = 100


@app.post('/_reset')
async def reset():
    """Drop all sequencer state, simulating a server restart (new epochs)."""
    global _store
    _store = SequencerStore()
    return {'ok': True}


@app.get('/stream')
async def stream(request: Request, last_event_id: str | None = Header(None)):
    """Emit sequenced `progress` events 1.._TOTAL, resuming via Last-Event-ID."""
    worker_id = request.query_params.get('worker_id', 'w1')
    seq = _store.get_or_create(worker_id)

    async def gen():
        for frame in resume_frames(last_event_id, seq):
            yield frame
        while seq.next_seq <= _TOTAL:
            yield format_event('progress', {'n': seq.next_seq}, seq)
            await asyncio.sleep(0.01)

    return StreamingResponse(gen(), media_type='text/event-stream')
