---
title: A2A Protocol
description: How AgentMesh implements the A2A Protocol specification
---

# A2A Protocol

AgentMesh Server is a production implementation of the [A2A (Agent-to-Agent) Protocol](https://a2a-protocol.org/), an open standard from the Linux Foundation.

## What is A2A?

The Agent-to-Agent Protocol defines how AI agents communicate, collaborate, and solve problems together. It provides:

- **Standardized discovery** via Agent Cards
- **Task-based communication** with JSON-RPC 2.0
- **Real-time streaming** via Server-Sent Events
- **Multi-turn conversations** with session state

## Specification Compliance

AgentMesh implements the complete A2A Protocol specification:

| Section | Feature | Status |
|---------|---------|--------|
| §5 | Agent Discovery (Agent Card) | ✅ Full |
| §6 | Protocol Data Objects | ✅ Full |
| §7 | JSON-RPC Methods | ✅ Full |
| §8 | Streaming (SSE) | ✅ Full |
| §9 | Common Workflows | ✅ Full |

## Agent Card

Every AgentMesh server exposes an Agent Card at `/.well-known/agent-card.json`:

```bash
curl https://agentmesh.run/.well-known/agent-card.json
```

```json
{
  "name": "AgentMesh Server",
  "description": "Production A2A coordination server",
  "url": "https://agentmesh.run",
  "version": "1.0.0",
  "provider": {
    "organization": "AgentMesh",
    "url": "https://agentmesh.run"
  },
  "capabilities": {
    "streaming": true,
    "pushNotifications": true,
    "stateTransitionHistory": true
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
  "authentication": {
    "schemes": ["bearer"]
  }
}
```

## JSON-RPC Methods

AgentMesh supports all standard A2A methods:

### tasks/send

Send a task to the agent.

```json
{
  "jsonrpc": "2.0",
  "method": "tasks/send",
  "params": {
    "id": "task-123",
    "message": {
      "role": "user",
      "parts": [{"text": "Analyze this code"}]
    }
  },
  "id": "1"
}
```

### tasks/sendSubscribe

Send a task and subscribe to streaming updates.

```json
{
  "jsonrpc": "2.0",
  "method": "tasks/sendSubscribe",
  "params": {
    "message": {
      "role": "user",
      "parts": [{"text": "Generate a report"}]
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
    "id": "task-123"
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
    "id": "task-123"
  },
  "id": "3"
}
```

## Learn More

- [A2A Protocol Specification](https://a2a-protocol.org/specification.md)
- [A2A Key Concepts](https://a2a-protocol.org/topics/key-concepts.md)
- [A2A and MCP](https://a2a-protocol.org/topics/a2a-and-mcp.md)
