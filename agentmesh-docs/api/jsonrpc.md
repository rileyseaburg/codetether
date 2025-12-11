---
title: JSON-RPC Methods
description: A2A Protocol JSON-RPC method reference
---

# JSON-RPC Methods

CodeTether implements the A2A Protocol JSON-RPC methods.

## Endpoint

```
POST /v1/a2a
Content-Type: application/json
```

## Methods

### tasks/send

Send a task to the agent.

### tasks/sendSubscribe

Send and subscribe to streaming updates.

### tasks/get

Get task status.

### tasks/cancel

Cancel a running task.

See [A2A Protocol Specification](https://a2a-protocol.org/specification.md) for full details.
