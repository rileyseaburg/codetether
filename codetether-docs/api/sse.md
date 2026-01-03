---
title: SSE Events
description: Server-Sent Events reference
---

# SSE Events

CodeTether uses Server-Sent Events for real-time task distribution to workers.

## Worker Task Stream

Workers connect to the task stream endpoint to receive task assignments in real-time:

```http
GET /v1/worker/tasks/stream
```

### Request Headers

| Header | Required | Description |
|--------|----------|-------------|
| `X-Codebases` | Yes | Comma-separated list of registered codebase IDs |
| `X-Capabilities` | Yes | Comma-separated list of worker capabilities |
| `worker_id` | Yes | Worker identifier |
| `Authorization` | No | Bearer token for authentication |
| `Accept` | Yes | Must be `text/event-stream` |

### Example Request

```http
GET /v1/worker/tasks/stream?worker_id=worker-123 HTTP/1.1
Host: api.codetether.run
Accept: text/event-stream
X-Codebases: my-project,api,backend
X-Capabilities: opencode,build,deploy,test
Authorization: Bearer <token>
```

## Event Types

| Event | Description | Payload |
|-------|-------------|---------|
| `connected` | SSE connection established | `{"message": "..."}` |
| `task_available` | New task available for worker | `{"task_id": "...", "title": "...", "codebase_id": "...", ...}` |
| `task` | Full task object pushed | Full task JSON |
| `keepalive` | Connection keepalive (every 30s) | `{}` |
| `error` | Error occurred | `{"message": "..."}` |

## Example Stream

```
event: connected
data: {"message":"SSE connection established"}

event: task_available
data: {"task_id":"task-abc-123","title":"Add unit tests","codebase_id":"my-project","priority":0}

event: keepalive
data: {}

event: task
data: {"id":"task-abc-123","title":"Add unit tests","codebase_id":"my-project",...}
```

## Routing

Tasks are routed to workers based on:

1. **Codebase matching**: Tasks with matching `codebase_id` are sent to workers with that codebase
2. **Global tasks**: Tasks with `codebase_id: "global"` are sent to all workers with global codebase registered
3. **Pending tasks**: Tasks with `codebase_id: "__pending__"` can be claimed by any worker
