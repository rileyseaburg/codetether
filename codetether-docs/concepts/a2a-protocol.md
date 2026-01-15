---
title: A2A Protocol
description: How CodeTether implements the A2A Protocol specification
---

# A2A Protocol

CodeTether Server is a production implementation of the [A2A (Agent-to-Agent) Protocol](https://a2a-protocol.org/), an open standard from the Linux Foundation.

## What is A2A?

The Agent-to-Agent Protocol defines how AI agents communicate, collaborate, and solve problems together. It provides:

- **Standardized discovery** via Agent Cards
- **Task-based communication** with JSON-RPC 2.0
- **Real-time streaming** via Server-Sent Events
- **Multi-turn conversations** with session state

## Official SDK Integration

CodeTether now uses the official A2A Python SDK (`a2a-sdk>=0.3.22`) from the [A2A Project](https://github.com/a2aproject/a2a-python). This provides:

- **Protocol compliance** - All data structures and methods match the official specification
- **Battle-tested streaming** - Robust SSE implementation with proper backpressure handling
- **Standard error codes** - Consistent error handling across all A2A implementations
- **Type safety** - Full Pydantic models for request/response validation

Our previous custom implementation has been replaced with thin wrappers around the SDK, ensuring interoperability with any A2A-compliant agent.

## Specification Compliance

CodeTether aims to be A2A-compliant and implements the core pieces used by this project:

| Section | Feature | Status |
|---------|---------|--------|
| §5 | Agent Discovery (Agent Card) | ✅ Full |
| §6 | Protocol Data Objects | ✅ Full |
| §7 | JSON-RPC Methods | ✅ Full |
| §8 | Streaming (SSE) | ✅ Full |
| §9 | Common Workflows | ✅ Full |

## Agent Card

Every CodeTether server exposes an Agent Card at `/.well-known/agent-card.json`:

```bash
curl https://api.codetether.run/.well-known/agent-card.json
```

```json
{
  "name": "CodeTether Server",
  "description": "Production A2A coordination server",
  "url": "https://api.codetether.run",
  "version": "1.0.0",
  "provider": {
    "organization": "CodeTether",
    "url": "https://codetether.run"
  },
  "capabilities": {
    "streaming": true,
    "push_notifications": true,
    "state_transition_history": true
  },
  "skills": [
    {
      "id": "task-coordination",
      "name": "Task Coordination",
      "description": "Coordinate tasks between multiple agents"
    },
    {
      "id": "code-assistance",
      "name": "Code Assistance",
      "description": "AI-powered coding assistance via OpenCode"
    }
  ],
  "authentication": [
    {"scheme": "bearer"}
  ]
}
```

## JSON-RPC Methods

CodeTether supports the following JSON-RPC methods:

### message/send

Send a task to the agent.

```json
{
  "jsonrpc": "2.0",
  "method": "message/send",
  "params": {
    "message": {
      "parts": [{"type": "text", "content": "Analyze this code"}]
    }
  },
  "id": "1"
}
```

### message/stream

Send a task and subscribe to streaming updates.

```json
{
  "jsonrpc": "2.0",
  "method": "message/stream",
  "params": {
    "message": {
      "parts": [{"type": "text", "content": "Generate a report"}]
    }
  },
  "id": "1"
}
```

### tasks/get

Get the current state of a task.

```json
{
  "jsonrpc": "2.0",
  "method": "tasks/get",
  "params": {
    "task_id": "task-123"
  },
  "id": "2"
}
```

### tasks/cancel

Cancel a running task.

```json
{
  "jsonrpc": "2.0",
  "method": "tasks/cancel",
  "params": {
    "task_id": "task-123"
  },
  "id": "3"
}
```

## Standard Endpoints

CodeTether exposes the following A2A-compliant endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/.well-known/agent-card.json` | GET | Agent discovery (A2A spec) |
| `/a2a/jsonrpc` | POST | JSON-RPC 2.0 endpoint |
| `/a2a/rest/message:send` | POST | REST binding for message/send |
| `/a2a/rest/message:stream` | POST | SSE streaming endpoint |
| `/a2a/rest/tasks/{id}` | GET | Get task status |
| `/a2a/rest/tasks/{id}:cancel` | POST | Cancel a task |

The JSON-RPC endpoint accepts all methods (`message/send`, `message/stream`, `tasks/get`, `tasks/cancel`) via a single URL, while the REST bindings provide more traditional HTTP semantics.

## Task States

Tasks in A2A follow a defined state machine:

```
                    ┌─────────────┐
                    │  submitted  │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ rejected │ │ working  │ │auth-req'd│
        └──────────┘ └────┬─────┘ └──────────┘
                          │
           ┌──────────────┼──────────────┐
           ▼              ▼              ▼
     ┌───────────┐  ┌───────────┐  ┌───────────┐
     │ completed │  │  failed   │  │input-req'd│
     └───────────┘  └───────────┘  └───────────┘
                          │
                          ▼
                    ┌───────────┐
                    │ cancelled │
                    └───────────┘
```

| State | Description | Terminal? |
|-------|-------------|-----------|
| `submitted` | Task received, awaiting processing | No |
| `working` | Agent is actively processing | No |
| `input-required` | Agent needs additional input | No |
| `auth-required` | Authentication/authorization needed | No |
| `completed` | Task finished successfully | **Yes** |
| `failed` | Task encountered an error | **Yes** |
| `cancelled` | Task was cancelled by client | **Yes** |
| `rejected` | Task was rejected by agent | **Yes** |

## Error Codes

The A2A protocol defines standard JSON-RPC error codes:

| Code | Name | Description |
|------|------|-------------|
| `-32001` | `TaskNotFound` | The specified task does not exist |
| `-32002` | `TaskNotCancellable` | Task is in a terminal state |
| `-32003` | `PushNotificationNotSupported` | Agent doesn't support push notifications |
| `-32004` | `UnsupportedOperation` | Requested operation not supported |
| `-32005` | `ContentTypeNotSupported` | Unsupported content type in message |
| `-32006` | `InvalidAgentResponse` | Agent returned malformed response |
| `-32007` | `AgentUnavailable` | Target agent is not reachable |
| `-32008` | `AuthenticationRequired` | Request requires authentication |
| `-32009` | `AuthorizationFailed` | Insufficient permissions |

Standard JSON-RPC errors (`-32600` to `-32700`) also apply for malformed requests.

## Learn More

- [A2A Protocol Specification](https://a2a-protocol.org/specification.md)
- [A2A Key Concepts](https://a2a-protocol.org/topics/key-concepts.md)
- [A2A and MCP](https://a2a-protocol.org/topics/a2a-and-mcp.md)
