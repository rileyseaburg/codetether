"""Live end-to-end proof of resumable SSE over a real killed TCP connection.

Spawns uvicorn on a real port, consumes the stream, abruptly drops the TCP
connection mid-stream (simulating an RST / black-holed path), reconnects with
the last processed Last-Event-ID, and asserts the full sequence 1.._TOTAL is
received exactly once with no gaps and no duplicates. This is the section 9
acceptance experiment for Phase 1 (gap recovery within window + epoch restart).
"""

import asyncio
import json
import socket

import httpx
import pytest
import uvicorn

from tests.live_sse_app import _TOTAL


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


class _Server:
    """Run the live SSE app in a background uvicorn server thread."""

    def __init__(self, port: int):
        config = uvicorn.Config(
            'tests.live_sse_app:app', host='127.0.0.1', port=port,
            log_level='error',
        )
        self.server = uvicorn.Server(config)
        self._task: asyncio.Task | None = None

    async def __aenter__(self):
        self._task = asyncio.create_task(self.server.serve())
        while not self.server.started:
            await asyncio.sleep(0.02)
        return self

    async def __aexit__(self, *exc):
        self.server.should_exit = True
        if self._task:
            await self._task


async def _consume_until(url: str, last_id: str | None, stop_after: int):
    """Consume up to `stop_after` progress events, then drop the connection.

    Returns (received_seqs, last_event_id_processed). Exiting the stream context
    tears the socket down abruptly, simulating a mid-stream disconnect.
    """
    headers = {'Last-Event-ID': last_id} if last_id else {}
    received: list[int] = []
    last_event_id = last_id
    buf = b''
    async with httpx.AsyncClient(timeout=10.0) as client:
        async with client.stream('GET', url, headers=headers) as resp:
            async for chunk in resp.aiter_bytes():
                buf += chunk
                while b'\n\n' in buf:
                    frame, buf = buf.split(b'\n\n', 1)
                    block = frame + b'\n\n'
                    if b'event: progress' not in block:
                        continue
                    eid = n = None
                    for line in block.split(b'\n'):
                        if line.startswith(b'id:'):
                            eid = line[3:].strip().decode()
                        elif line.startswith(b'data:'):
                            n = json.loads(line[5:].strip())['n']
                    if n is not None:
                        received.append(n)
                        last_event_id = eid
                    if len(received) >= stop_after:
                        return received, last_event_id
    return received, last_event_id


async def _first_frames_raw(url: str, last_id: str | None, limit: int) -> bytes:
    """Return at least `limit` bytes of raw frames, then drop the connection."""
    headers = {'Last-Event-ID': last_id} if last_id else {}
    buf = b''
    async with httpx.AsyncClient(timeout=10.0) as client:
        async with client.stream('GET', url, headers=headers) as resp:
            async for chunk in resp.aiter_bytes():
                buf += chunk
                if len(buf) >= limit:
                    return buf
    return buf


@pytest.mark.asyncio
async def test_killed_connection_resumes_without_loss():
    port = _free_port()
    url = f'http://127.0.0.1:{port}/stream?worker_id=live1'
    async with _Server(port):
        # First leg: process half, then abruptly drop the connection.
        leg1, last_id = await _consume_until(url, None, stop_after=50)
        assert leg1 == list(range(1, 51))
        assert last_id is not None

        # Reconnect with Last-Event-ID; server replays the gap then continues.
        leg2, _ = await _consume_until(url, last_id, stop_after=50)

    combined = leg1 + leg2
    # Exactly-once, in-order, no gaps across the kill boundary.
    assert combined == list(range(1, _TOTAL + 1)), (
        f'expected 1..{_TOTAL} exactly once; got {len(combined)} items, '
        f'duplicates={len(combined) - len(set(combined))}'
    )


@pytest.mark.asyncio
async def test_epoch_restart_forces_resync_not_corrupt_replay():
    port = _free_port()
    base = f'http://127.0.0.1:{port}'
    url = f'{base}/stream?worker_id=live2'
    async with _Server(port):
        # Establish an epoch and process some events.
        _, last_id = await _consume_until(url, None, stop_after=10)
        assert last_id is not None

        # Simulate a server restart: all sequencer state (epochs) reset.
        async with httpx.AsyncClient(timeout=10.0) as c:
            await c.post(f'{base}/_reset')

        # Reconnect with the now-stale Last-Event-ID. The fresh epoch cannot
        # match, so the server must emit resync-required, never a corrupt
        # replay against a different sequence space.
        raw = await _first_frames_raw(url, last_id, limit=200)

    assert b'event: resync-required' in raw
    assert b'epoch_mismatch' in raw
