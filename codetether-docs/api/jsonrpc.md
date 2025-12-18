---
title: JSON-RPC Methods
description: A2A Protocol JSON-RPC method reference
---

# JSON-RPC Methods

CodeTether implements the A2A Protocol JSON-RPC methods.

## Endpoint

```
POST /v1/a2a
POST /  (alias)
Content-Type: application/json
```

## Methods

### message/send

Send a message to the agent.

### message/stream

Send a message and receive streaming updates (SSE-style payloads).

### tasks/get

Get task status.

### tasks/cancel

Cancel a running task.

### tasks/resubscribe

Resubscribe to updates for an existing task.

See [A2A Protocol Specification](https://a2a-protocol.org/specification.md) for full details.
