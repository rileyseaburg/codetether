"""Test MCP router root endpoint advertises expected /mcp/v1 endpoints."""

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from a2a_server.mcp_router import create_mcp_router, MCPToolHandler


@pytest.fixture
def mcp_client() -> TestClient:
    """Create test client with MCP router mounted."""
    app = FastAPI()
    handler = MCPToolHandler(a2a_server=None)
    app.include_router(create_mcp_router(handler))
    return TestClient(app)


def test_mcp_root_advertises_v1_endpoints(mcp_client: TestClient) -> None:
    """Verify GET /mcp returns expected /mcp/v1 endpoint paths."""
    resp = mcp_client.get("/mcp")
    assert resp.status_code == 200

    data = resp.json()
    assert data["jsonrpc"] == "2.0"
    assert data["protocol"] == "mcp"

    endpoints = data["endpoints"]
    assert endpoints["sse"] == "/mcp/v1/sse"
    assert endpoints["message"] == "/mcp/v1/message"
    assert endpoints["rpc"] == "/mcp/v1/rpc"
    assert endpoints["tools"] == "/mcp/v1/tools"
