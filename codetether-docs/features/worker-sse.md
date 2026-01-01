# Worker SSE Push Notifications

Worker SSE (Server-Sent Events) enables push-based task distribution, allowing workers to receive tasks in real-time without polling.

## Overview

Traditional workers poll the server for new tasks at intervals. SSE push notifications:

- **Instant task delivery** when tasks are created
- **Reduced server load** - no polling overhead
- **Lower latency** - workers start tasks immediately
- **Connection management** - automatic reconnection on failure

## Architecture

```
A2A Server
    ↓ (SSE Push)
Worker 1 (connected)
Worker 2 (connected)
Worker 3 (connected)
```

## How It Works

1. **Worker connects** to SSE endpoint: `GET /v1/workers/sse`
2. **Server keeps connection** open indefinitely
3. **When task created** → Server pushes event to all connected workers
4. **Workers receive** `{ "type": "new_task", "task_id": "..." }`
5. **First worker** to claim task gets it (race condition handled)

## Worker SSE Client

### Python Implementation

```python
import requests

def connect_sse_worker(worker_id: str, server_url: str = "http://localhost:8000"):
    """Connect to SSE endpoint and listen for task notifications."""
    url = f"{server_url}/v1/workers/sse?worker_id={worker_id}"

    with requests.get(url, stream=True) as response:
        for line in response.iter_lines():
            if line:
                event = parse_sse_event(line)
                handle_event(event)

def parse_sse_event(line: bytes) -> dict:
    """Parse SSE event line."""
    if line.startswith(b"data: "):
        return json.loads(line[6:])
    return {}

def handle_event(event: dict):
    """Handle incoming SSE event."""
    if event.get("type") == "new_task":
        task_id = event.get("task_id")
        print(f"New task available: {task_id}")
        claim_and_execute_task(task_id)
```

See [examples/worker_sse_client.py](https://github.com/rileyseaburg/codetether/blob/main/examples/worker_sse_client.py) for a complete example.

## SSE Event Types

| Event Type | Description | Payload |
|------------|-------------|---------|
| `new_task` | New task created | `{ "task_id": "uuid", "title": "...", "priority": 0 }` |
| `task_update` | Task status changed | `{ "task_id": "uuid", "status": "working" }` |
| `keepalive` | Connection keepalive | `{}` (sent every 30s) |
| `error` | Error occurred | `{ "message": "..." }` |

## Server Configuration

### Enable SSE

SSE is enabled by default. Configure via environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `WORKER_SSE_ENABLED` | Enable SSE endpoint | `true` |
| `WORKER_SSE_KEEPALIVE` | Keepalive interval (seconds) | `30` |
| `WORKER_SSE_TIMEOUT` | Worker idle timeout (seconds) | `300` |

### Task Creation Hook

When SSE is enabled, tasks are automatically pushed to workers:

```python
from a2a_server.worker_sse import setup_task_creation_hook

# Hook is automatically called when task is created
setup_task_creation_hook(task_manager, notify_workers_of_new_task)
```

## Connecting Workers

### Registration

Workers register to receive SSE notifications:

```bash
# Register worker and get SSE URL
curl -X POST http://localhost:8000/v1/workers \
  -H "Content-Type: application/json" \
  -d '{
    "worker_id": "worker-123",
    "capabilities": ["build", "test"],
    "sse_enabled": true
  }'
```

Response:
```json
{
  "worker_id": "worker-123",
  "sse_url": "http://localhost:8000/v1/workers/sse?worker_id=worker-123",
  "registered": true
}
```

### Event Stream

```bash
curl -N "http://localhost:8000/v1/workers/sse?worker_id=worker-123"
```

Output:
```
event: keepalive
data: {}

event: new_task
data: {"task_id":"task-abc","title":"Build component","priority":0}

event: task_update
data: {"task_id":"task-abc","status":"completed"}
```

## Automatic Reconnection

Workers should implement exponential backoff reconnection:

```python
import time
import requests

def connect_with_retry(worker_id: str, max_retries: int = 10):
    retry_count = 0

    while retry_count < max_retries:
        try:
            return connect_sse_worker(worker_id)
        except requests.exceptions.ConnectionError:
            retry_count += 1
            wait_time = min(2 ** retry_count, 60)  # Max 60s
            print(f"Connection lost, retrying in {wait_time}s...")
            time.sleep(wait_time)

    raise Exception("Max retries exceeded")
```

## Claiming Tasks

When a worker receives a `new_task` event, it should claim the task:

```bash
# Claim the task (atomic operation)
curl -X POST http://localhost:8000/v1/tasks/{task_id}/claim \
  -H "Content-Type: application/json" \
  -d '{"worker_id": "worker-123"}'
```

Response:
```json
{
  "task_id": "task-abc",
  "status": "working",
  "claimed_by": "worker-123",
  "claimed_at": "2025-01-01T12:00:00Z"
}
```

If another worker already claimed it:
```json
{
  "error": "Task already claimed",
  "claimed_by": "worker-456"
}
```

## Monitoring

### Connected Workers

```bash
# List connected workers
curl http://localhost:8000/v1/workers/connected

# Output:
# [
#   {"worker_id": "worker-123", "connected_at": "...", "last_heartbeat": "..."},
#   {"worker_id": "worker-456", "connected_at": "...", "last_heartbeat": "..."}
# ]
```

### Worker Status

```bash
# Check specific worker status
curl http://localhost:8000/v1/workers/{worker_id}/status
```

## Troubleshooting

### Workers not receiving tasks?

Check SSE endpoint health:
```bash
curl -N "http://localhost:8000/v1/workers/sse?worker_id=test"
```

### Connection drops frequently?

Increase keepalive interval:
```bash
export WORKER_SSE_KEEPALIVE=60
```

### Tasks not being pushed?

Verify task creation hook is registered:
```bash
# Check logs
kubectl logs deployment/a2a-server | grep "worker_sse"
```

### Multiple workers claiming same task?

This is expected behavior. Use the claim API to ensure atomic assignment:
```bash
POST /v1/tasks/{task_id}/claim
```

## See Also

- [Distributed Workers](distributed-workers.md)
- [Agent Worker](agent-worker.md)
- [Task Management](concepts/task-management.md)
