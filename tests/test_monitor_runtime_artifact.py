import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from a2a_server.monitor_api import (
    _default_vm_workspace_download_url,
    agent_router,
)
import a2a_server.monitor_api as monitor_api


def test_default_vm_workspace_download_url_uses_control_plane(monkeypatch):
    monkeypatch.delenv('VM_WORKSPACE_CODETETHER_DOWNLOAD_URL', raising=False)
    monkeypatch.setenv('A2A_AGENT_URL', 'https://api.codetether.run/')
    assert (
        _default_vm_workspace_download_url()
        == 'https://api.codetether.run/v1/agent/runtime/codetether'
    )


@pytest.mark.asyncio
async def test_runtime_artifact_download_streams_from_minio(monkeypatch):
    app = FastAPI()
    app.include_router(agent_router)

    payload = b'codetether-runtime'

    class _Response:
        def stream(self, _chunk_size):
            yield payload

        def close(self):
            return None

        def release_conn(self):
            return None

    class _Minio:
        def stat_object(self, bucket, path):
            assert bucket == monitor_api.MINIO_BUCKET
            assert path == 'runtime/codetether.tar.gz'
            return object()

        def get_object(self, bucket, path):
            assert bucket == monitor_api.MINIO_BUCKET
            assert path == 'runtime/codetether.tar.gz'
            return _Response()

    monkeypatch.setattr(monitor_api, '_get_minio_client', lambda: _Minio())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test') as client:
        response = await client.get('/v1/agent/runtime/codetether')

    assert response.status_code == 200
    assert response.content == payload
    assert (
        response.headers['content-disposition']
        == 'attachment; filename="codetether.tar.gz"'
    )
