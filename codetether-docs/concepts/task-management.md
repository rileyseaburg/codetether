---
title: Task Management
description: How CodeTether manages agent tasks
---

# Task Management

CodeTether provides comprehensive task management for AI agent workflows.

## Task Lifecycle

```mermaid
stateDiagram-v2
    [*] --> Pending: Create
    Pending --> Running: Assigned
    Running --> Completed: Success
    Running --> Failed: Error
    Pending --> Cancelled: Cancel
    Running --> Cancelled: Cancel
    Completed --> [*]
    Failed --> [*]
    Cancelled --> [*]
```

## Task States

| State | Description |
|-------|-------------|
| `pending` | Task created, waiting for worker |
| `running` | Worker is executing the task |
| `completed` | Task finished successfully |
| `failed` | Task encountered an error |
| `cancelled` | Task was cancelled |

## Creating Tasks

### Via A2A Protocol

```json
{
  "jsonrpc": "2.0",
  "method": "message/send",
  "params": {
    "message": {
      "parts": [{"type": "text", "content": "Analyze this codebase"}]
    }
  },
  "id": "1"
}
```

### Via OpenCode API

```bash
curl -X POST /v1/opencode/codebases/{id}/tasks \
  -d '{"title": "Add tests", "prompt": "Add unit tests"}'
```

## Task Priority

Tasks can be prioritized (higher number = higher priority):

```json
{
  "title": "Urgent fix",
  "prompt": "Fix the authentication bug",
  "priority": 10
}
```

## Next Steps

- [API Reference](../api/overview.md)
- [Distributed Workers](../features/distributed-workers.md)
