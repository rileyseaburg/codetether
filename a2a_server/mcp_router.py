"""
MCP Router - FastAPI router for MCP protocol endpoints.

This module provides MCP (Model Context Protocol) endpoints that can be mounted
on the main A2A server, eliminating the need for a separate MCP server port.

The MCP protocol allows AI agents and tools to communicate using JSON-RPC
over HTTP with optional SSE streaming.
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

logger = logging.getLogger(__name__)

# Create the MCP router
mcp_router = APIRouter(prefix='/mcp', tags=['MCP Protocol'])


def create_mcp_router(mcp_handler: 'MCPToolHandler') -> APIRouter:
    """
    Create an MCP router with the given tool handler.

    Args:
        mcp_handler: Instance of MCPToolHandler that processes tool calls

    Returns:
        FastAPI APIRouter with MCP endpoints
    """
    router = APIRouter(prefix='/mcp', tags=['MCP Protocol'])

    @router.get('')
    async def mcp_root(request: Request):
        """MCP SSE endpoint root - redirects to SSE endpoint or returns info."""
        accept = request.headers.get('accept', '')
        if 'text/event-stream' in accept:
            return await handle_sse(request)
        return {
            'jsonrpc': '2.0',
            'protocol': 'mcp',
            'version': '1.0.0',
            'capabilities': {'tools': True, 'sse': True},
            'endpoints': {
                'sse': '/mcp/v1/sse',
                'message': '/mcp/v1/message',
                'rpc': '/mcp/v1/rpc',
                'tools': '/mcp/v1/tools',
            },
        }

    @router.post('')
    async def mcp_post(request: Request):
        """Handle POST messages to /mcp for SSE transport."""
        return await handle_rpc(request)

    @router.get('/v1/sse')
    async def handle_sse(request: Request):
        """Handle SSE connections for MCP."""
        # Build the full message endpoint URL from the request
        # This is required by MCP SSE transport spec
        scheme = request.headers.get('x-forwarded-proto', request.url.scheme)
        host = request.headers.get(
            'x-forwarded-host', request.headers.get('host', request.url.netloc)
        )
        message_url = f'{scheme}://{host}/mcp/v1/message'

        async def event_generator():
            try:
                # Send the endpoint URL that clients should POST messages to
                yield f'event: endpoint\ndata: {message_url}\n\n'
                while True:
                    await asyncio.sleep(30)
                    yield f'event: ping\ndata: {json.dumps({"timestamp": datetime.now().isoformat()})}\n\n'
            except asyncio.CancelledError:
                logger.info('SSE connection closed')
                raise
            except Exception as e:
                logger.error(f'Error in SSE stream: {e}')
                raise

        return StreamingResponse(
            event_generator(),
            media_type='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'X-Accel-Buffering': 'no',
            },
        )

    @router.get('/v1/tools')
    async def list_tools():
        """List available MCP tools."""
        tools = mcp_handler.get_tools()
        return {'tools': tools}

    @router.post('/v1/message')
    async def handle_message(request: Request):
        """Handle POST messages from SSE clients."""
        return await handle_rpc(request)

    @router.post('/v1/rpc')
    async def handle_rpc(request: Request):
        """Handle MCP JSON-RPC requests."""
        try:
            # Validate MCP Protocol header if present
            protocol_version = request.headers.get('mcp-protocol-version')
            if protocol_version and protocol_version not in (
                '2025-06-18',
                '2024-11-05',
                '2025-03-26',
            ):
                return JSONResponse(
                    {'error': 'Unsupported MCP-Protocol-Version'},
                    status_code=400,
                )

            # GET requests: return SSE stream
            if request.method == 'GET':
                return await handle_sse(request)

            # Read request body
            body_bytes = await request.body()
            if not body_bytes:
                raise HTTPException(
                    status_code=400,
                    detail='Empty request body - expected JSON-RPC payload',
                )

            try:
                payload = json.loads(body_bytes.decode('utf-8'))
            except Exception:
                raise HTTPException(
                    status_code=400, detail='Invalid JSON in request body'
                )

            method = payload.get('method')
            request_id = payload.get('id')
            params = payload.get('params', {}) or {}

            # Notification (no id): process in background
            if request_id is None:
                asyncio.create_task(
                    mcp_handler.call_tool_from_payload(method, params)
                )
                return JSONResponse(status_code=202, content=None)

            # Handle initialize
            if method == 'initialize':
                return JSONResponse(
                    content={
                        'jsonrpc': '2.0',
                        'id': request_id,
                        'result': {
                            'protocolVersion': '2025-06-18',
                            'capabilities': {'tools': {}},
                            'serverInfo': {
                                'name': 'a2a-server',
                                'version': '1.0.0',
                            },
                        },
                    }
                )

            # Handle tools/list
            if method == 'tools/list':
                tools = mcp_handler.get_tools()
                return JSONResponse(
                    content={
                        'jsonrpc': '2.0',
                        'id': request_id,
                        'result': {'tools': tools},
                    }
                )

            # Handle tools/call
            if method == 'tools/call':
                try:
                    result = await mcp_handler.call_tool(
                        params.get('name'), params.get('arguments', {})
                    )
                    # MCP spec requires tools/call result to be wrapped in content array
                    return JSONResponse(
                        content={
                            'jsonrpc': '2.0',
                            'id': request_id,
                            'result': {
                                'content': [
                                    {
                                        'type': 'text',
                                        'text': json.dumps(result, default=str),
                                    }
                                ]
                            },
                        }
                    )
                except Exception as e:
                    return JSONResponse(
                        content={
                            'jsonrpc': '2.0',
                            'id': request_id,
                            'error': {'code': -32603, 'message': str(e)},
                        },
                        status_code=500,
                    )

            # Unknown method
            return JSONResponse(
                content={
                    'jsonrpc': '2.0',
                    'id': request_id,
                    'error': {
                        'code': -32601,
                        'message': f'Method not found: {method}',
                    },
                },
                status_code=400,
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f'Error handling RPC: {e}')
            return JSONResponse(
                {
                    'jsonrpc': '2.0',
                    'error': {'code': -32603, 'message': str(e)},
                },
                status_code=500,
            )

    # REST API endpoints for task queue (used by monitor UI)
    @router.get('/v1/tasks')
    async def list_tasks_rest(status: Optional[str] = None):
        """REST endpoint to list tasks."""
        try:
            result = await mcp_handler.list_tasks(
                {'status': status} if status else {}
            )
            return result
        except Exception as e:
            logger.error(f'Error listing tasks: {e}')
            raise HTTPException(status_code=500, detail=str(e))

    @router.post('/v1/tasks')
    async def create_task_rest(request: Request):
        """REST endpoint to create a task."""
        try:
            body = await request.json()
            result = await mcp_handler.create_task(body)
            return result
        except Exception as e:
            logger.error(f'Error creating task: {e}')
            raise HTTPException(status_code=500, detail=str(e))

    @router.get('/v1/tasks/{task_id}')
    async def get_task_rest(task_id: str):
        """REST endpoint to get a specific task."""
        try:
            result = await mcp_handler.get_task({'task_id': task_id})
            if 'error' in result:
                raise HTTPException(status_code=404, detail=result['error'])
            return result
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f'Error getting task: {e}')
            raise HTTPException(status_code=500, detail=str(e))

    return router


class MCPToolHandler:
    """
    Handler for MCP tool calls.

    This class contains all the tool definitions and handlers that were
    previously in MCPHTTPServer. It can be used with either the router
    or the standalone server.
    """

    def __init__(self, a2a_server=None):
        self.a2a_server = a2a_server
        # Import here to avoid circular imports
        from .mcp_http_server import MCPHTTPServer

        # Reuse the existing MCPHTTPServer for tool handling
        self._delegate = MCPHTTPServer(a2a_server=a2a_server)

    def get_tools(self) -> List[Dict[str, Any]]:
        """Get list of available MCP tools."""
        return self._delegate._get_tools_from_a2a_server()

    async def call_tool(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute an MCP tool."""
        return await self._delegate._call_tool(tool_name, arguments)

    async def call_tool_from_payload(
        self, method: str, params: Dict[str, Any]
    ) -> None:
        """Execute a tool call from a JSON-RPC payload (notification)."""
        await self._delegate._call_tool_from_payload(method, params)

    async def list_tasks(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """List tasks."""
        return await self._delegate._list_tasks(args)

    async def create_task(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Create a task."""
        return await self._delegate._create_task(args)

    async def get_task(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get a task."""
        return await self._delegate._get_task(args)
