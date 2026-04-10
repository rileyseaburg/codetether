---
title: Real-time Streaming
description: SSE-based real-time output streaming
---

# Real-time Streaming

CodeTether provides real-time streaming of agent output via Server-Sent Events (SSE).

## Connecting

```javascript
const events = new EventSource('/v1/agent/codebases/{id}/events');

events.onmessage = (e) => {
  console.log(JSON.parse(e.data));
};
```

## Event Types

- `output` - Agent text output
- `tool_use` - Tool invocation
- `file_change` - File modifications
- `complete` - Task completed
- `error` - Error occurred

See [SSE Events](../api/sse.md) for details.
