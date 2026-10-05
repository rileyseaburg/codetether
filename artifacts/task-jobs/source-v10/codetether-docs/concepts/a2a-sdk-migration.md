# A2A SDK Migration Guide

## Overview

CodeTether v1.2.0 introduces full compliance with the A2A Protocol v0.3 specification using the official `a2a-sdk` from Google. This migration ensures that CodeTether can interoperate with any A2A-compliant agent or client while preserving all existing functionality.

## What Changed

### New Dependencies

The following dependency was added to `pyproject.toml`:

```toml
"a2a-sdk[http-server,postgresql]>=0.3.22"
```

This brings in:
- Core A2A protocol types and validation
- HTTP server utilities for JSON-RPC endpoints
- PostgreSQL storage adapter for task persistence

### New Files

| File | Purpose |
|------|---------|
| `a2a_server/a2a_executor.py` | Bridges A2A SDK to our task queue, translating between A2A requests and internal task operations |
| `a2a_server/a2a_agent_card.py` | Standard agent card endpoint serving `/.well-known/agent-card.json` |
| `a2a_server/a2a_router.py` | A2A protocol router handling JSON-RPC and REST endpoints |
| `a2a_server/a2a_types.py` | Task state mapping between internal states and A2A protocol states |
| `a2a_server/a2a_errors.py` | A2A error codes and exception handling |

### New Endpoints

| Endpoint | Description |
|----------|-------------|
| `/.well-known/agent-card.json` | Agent discovery endpoint per A2A spec |
| `/a2a/jsonrpc` | JSON-RPC 2.0 endpoint for A2A protocol methods |
| `/a2a/rest/*` | RESTful endpoints for task operations |

### Task State Alignment

The internal task states have been mapped to A2A protocol states:

| Internal State | A2A State | Description |
|----------------|-----------|-------------|
| `pending` | `submitted` | Task created, awaiting processing |
| `working` | `working` | Task actively being processed |
| `completed` | `completed` | Task finished successfully |
| `failed` | `failed` | Task encountered an error |
| `cancelled` | `canceled` | Task was cancelled by user |

## Backward Compatibility

All existing functionality remains fully operational:

- **MCP Tools**: Existing MCP tools at `/mcp` continue to work unchanged
- **Worker SSE Push**: The Server-Sent Events push system for workers is unchanged
- **Custom Extensions**: CodeTether-specific extensions are preserved:
  - `send_to_agent` for targeted agent messaging
  - Capability-based routing
  - Priority queuing
  - Conversation threading

## Using the A2A Endpoints

### 1. Discovering the Agent Card

```bash
curl https://your-codetether-server/.well-known/agent-card.json
```

Response:
```json
{
  "name": "CodeTether",
  "description": "A2A-compliant task queue and agent coordination server",
  "url": "https://your-codetether-server",
  "capabilities": {
    "streaming": true,
    "pushNotifications": true
  },
  "skills": [
    {
      "id": "task-management",
      "name": "Task Management",
      "description": "Create, monitor, and manage async tasks"
    }
  ]
}
```

### 2. Sending a Message via JSON-RPC

```bash
curl -X POST https://your-codetether-server/a2a/jsonrpc \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [
          {"text": "Analyze the codebase structure"}
        ]
      }
    }
  }'
```

Response:
```json
{
  "jsonrpc": "2.0",
  "id": "1",
  "result": {
    "id": "task-abc123",
    "status": {
      "state": "submitted"
    }
  }
}
```

### 3. Streaming Responses

For streaming responses, use the `message/stream` method:

```bash
curl -X POST https://your-codetether-server/a2a/jsonrpc \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "message/stream",
    "params": {
      "message": {
        "role": "user",
        "parts": [
          {"text": "Generate a detailed report"}
        ]
      }
    }
  }'
```

### 4. Getting Task Status

```bash
curl -X POST https://your-codetether-server/a2a/jsonrpc \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "tasks/get",
    "params": {
      "id": "task-abc123"
    }
  }'
```

Response:
```json
{
  "jsonrpc": "2.0",
  "id": "1",
  "result": {
    "id": "task-abc123",
    "status": {
      "state": "completed",
      "message": {
        "role": "agent",
        "parts": [
          {"text": "Analysis complete. The codebase contains..."}
        ]
      }
    }
  }
}
```

## Interoperability

With A2A SDK integration, CodeTether is now fully interoperable with the A2A ecosystem:

### Compatible Clients

Any A2A-compliant client can connect to CodeTether, including:
- Google's A2A reference clients
- Other A2A-enabled agent frameworks
- Custom clients implementing the A2A protocol

### Agent Discovery

Other agents can discover CodeTether through:
1. The standard `/.well-known/agent-card.json` endpoint
2. Manual registration in agent directories
3. DNS-based discovery (if configured)

### Multi-Agent Workflows

CodeTether can participate in multi-agent workflows:

```python
from a2a_sdk import A2AClient

# Connect to CodeTether
client = A2AClient("https://your-codetether-server")

# Discover capabilities
card = await client.get_agent_card()
print(f"Connected to {card.name} with skills: {card.skills}")

# Send a task
result = await client.send_message("Process this data")
print(f"Task {result.id} status: {result.status.state}")
```

### Protocol Compliance

CodeTether implements the following A2A protocol methods:
- `message/send` - Send a message and create a task
- `message/stream` - Stream task responses
- `tasks/get` - Get task status
- `tasks/cancel` - Cancel a running task
- `tasks/list` - List tasks (CodeTether extension)

## Migration Checklist

If you're upgrading from a previous version:

- [ ] Update dependencies: `pip install -U codetether`
- [ ] Run database migrations: `alembic upgrade head`
- [ ] Verify agent card is accessible at `/.well-known/agent-card.json`
- [ ] Test existing MCP integrations still work
- [ ] Update any hardcoded endpoint URLs if needed
- [ ] Review and update CORS settings for new endpoints

## Further Reading

- [A2A Protocol Specification](https://github.com/google/a2a)
- [CodeTether Architecture](./architecture.md)
- [Task Queue Documentation](./task-queue.md)
