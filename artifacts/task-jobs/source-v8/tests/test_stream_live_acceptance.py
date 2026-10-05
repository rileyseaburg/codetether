"""§9 acceptance: live SSE resume against a real uvicorn socket server.

Runs the real worker_sse_router under uvicorn on a loopback port, streams the
SSE response over a real TCP connection, pushes sequenced events, drops the
socket mid-stream, reconnects with Last-Event-ID, and asserts real gap replay
over the wire. See docs/transport-phase1-wire-contract.md section 9.
"""

import asyncio
import socket
import threading

import httpx
import pytest
import uvicorn
from fastapi import FastAPI

from a2a_server.worker_sse import worker_sse_router, get_worker_registry


def _free_port() -> int:
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port


class _Server:
    def __init__(self, app: FastAPI, port: int):
        cfg = uvicorn.Config(app, host='127.0.0.1', port=port, log_level='error')
        self._server = uvicorn.Server(cfg)
        self._thread = threading.Thread(target=self._server.run, daemon=True)

    def start(self):
        self._thread.start()

    async def wait_ready(self):
        for _ in range(100):
            if self._server.started:
                return
            await asyncio.sleep(0.05)
        raise RuntimeError('server did not start')

    def stop(self):
        self._server.should_exit = True
        self._thread.join(timeout=5)


async def _collect_ids(resp, count):
    ids: list[str] = []
    async for line in resp.aiter_lines():
        if line.startswith('id:'):
            ids.append(line.split('id:', 1)[1].strip())
            if len(ids) >= count:
                return ids
    return ids


@pytest.mark.asyncio
async def test_live_reconnect_replays_gap_over_real_socket():
    app = FastAPI()
    app.include_router(worker_sse_router)
    port = _free_port()
    server = _Server(app, port)
    server.start()
    await server.wait_ready()
    registry = get_worker_registry()
    worker_id = 'live-socket-worker'
    base = f'http://127.0.0.1:{port}'
    url = '/v1/worker/tasks/stream?agent_name=build&worker_id=' + worker_id

    try:
        async with httpx.AsyncClient(base_url=base, timeout=10) as client:
            async with client.stream('GET', url) as resp:
                assert resp.status_code == 200

                async def push():
                    for _ in range(40):
                        if registry._workers.get(worker_id):
                            break
                        await asyncio.sleep(0.05)
                    for pct in (10, 20, 30):
                        await registry.push_progress(worker_id, {'pct': pct})
                        await asyncio.sleep(0.02)

                pusher = asyncio.create_task(push())
                first = await asyncio.wait_for(_collect_ids(resp, 3), timeout=8)
                await pusher

        epoch = first[0].split('.')[0]
        assert first == [f'{epoch}.1', f'{epoch}.2', f'{epoch}.3']

        # Reconnect having processed seq 1; expect replay of 2 and 3.
        async with httpx.AsyncClient(base_url=base, timeout=10) as client:
            headers = {'Last-Event-ID': f'{epoch}.1'}
            async with client.stream('GET', url, headers=headers) as resp:
                second = await asyncio.wait_for(
                    _collect_ids(resp, 2), timeout=8
                )
        assert second == [f'{epoch}.2', f'{epoch}.3']
    finally:
        server.stop()
