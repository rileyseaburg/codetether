---
title: SSE Events
description: Server-Sent Events reference
---

# SSE Events

CodeTether uses Server-Sent Events for real-time streaming.

## Connecting

```javascript
const events = new EventSource('/v1/opencode/codebases/{id}/events');
```

## Event Types

| Event | Description |
|-------|-------------|
| `output` | Agent text output |
| `tool_use` | Tool invocation |
| `file_change` | File modifications |
| `status` | Status change |
| `complete` | Task completed |
| `error` | Error occurred |

## Example

```javascript
events.addEventListener('output', (e) => {
  const data = JSON.parse(e.data);
  console.log(data.content);
});
```
