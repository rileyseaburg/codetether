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

## Learn More

- [A2A Protocol Specification](https://a2a-protocol.org/specification.md)
- [A2A Key Concepts](https://a2a-protocol.org/topics/key-concepts.md)
- [A2A and MCP](https://a2a-protocol.org/topics/a2a-and-mcp.md)
