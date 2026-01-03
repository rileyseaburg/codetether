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

1. **Worker connects** to SSE endpoint: `GET /v1/worker/tasks/stream`
2. **Server keeps connection** open indefinitely
3. **When task created** → Server pushes event to all connected workers
4. **Workers receive** `{ "type": "task_available", "task_id": "..." }`
5. **First worker** to claim task gets it (race condition handled)

## Worker SSE Client

### Python Implementation

```python
import requests

def connect_sse_worker(worker_id: str, server_url: str = "http://localhost:8000"):
    """Connect to SSE endpoint and listen for task notifications."""
    url = f"{server_url}/v1/worker/tasks/stream"
    headers = {
        "X-Codebases": "my-project,api",
        "X-Capabilities": "opencode,build,deploy,test"
    }

    with requests.get(url, headers=headers, params={"worker_id": worker_id}, stream=True) as response:
        for line in response.iter_lines():
            if line:
                event = parse_sse_event(line)
                handle_event(event)

def parse_sse_event(line: bytes) -> dict:
    """Parse SSE event line."""
    if line.startswith(b"event: "):
        event_type = line[7:].decode().strip()
        return {"event": event_type}
    if line.startswith(b"data: "):
        return json.loads(line[6:])
    return {}

def handle_event(event: dict):
    """Handle incoming SSE event."""
    event_type = event.get("event")
    data = event.get("data", {})

    if event_type == "task_available":
        task_id = data.get("task_id")
        print(f"New task available: {task_id}")
        claim_and_execute_task(task_id)
```

See [examples/worker_sse_client.py](https://github.com/rileyseaburg/codetether/blob/main/examples/worker_sse_client.py) for a complete example.

## SSE Event Types

| Event Type | Description | Payload |
|------------|-------------|---------|
| `task_available` | New task available for assignment | `{ "task_id": "uuid", "title": "...", "priority": 0, "codebase_id": "..." }` |
| `task` | Task details pushed to worker | Full task object |
| `connected` | Connection established | `{ "message": "..." }` |
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
# Register worker and get worker ID
curl -X POST http://localhost:8000/v1/opencode/workers/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "worker-123",
    "capabilities": ["opencode", "build", "test"],
    "hostname": "dev-vm.internal"
  }'
```

Response:
```json
{
  "worker_id": "abc123",
  "name": "worker-123",
  "registered": true
}
```

### Event Stream

```bash
# Connect to SSE stream with headers for routing
curl -N "http://localhost:8000/v1/worker/tasks/stream" \
  -H "X-Codebases: my-project,api" \
  -H "X-Capabilities: opencode,build,deploy,test" \
  -H "worker_id: worker-123"
```

Output:
```
event: connected
data: {"message":"SSE connection established"}

event: task_available
data: {"task_id":"task-abc","title":"Build component","codebase_id":"my-project","priority":0}

event: task
data: {"id":"task-abc","title":"Build component",...}

event: keepalive
data: {}
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

## Task Routing

Workers receive tasks based on:

1. **Codebase Matching**: Tasks are routed to workers with matching `codebase_id`
2. **Global Tasks**: Tasks with `codebase_id: "global"` are sent to all workers
3. **Pending Registration**: Tasks with `codebase_id: "__pending__"` can be claimed by any worker

### Header-Based Routing

Workers send their registered codebases and capabilities via headers:

```
X-Codebases: my-project,api,backend
X-Capabilities: opencode,build,deploy,test
```

The server uses these headers to route tasks to the appropriate workers.

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

1. Verify SSE endpoint health:
   ```bash
   curl -N "http://localhost:8000/v1/worker/tasks/stream" \
     -H "X-Codebases: test" \
     -H "X-Capabilities: opencode,build" \
     -H "worker_id: test"
   ```

2. Check that workers are sending correct headers:
   - `X-Codebases`: Comma-separated list of registered codebase IDs
   - `X-Capabilities`: Comma-separated list of worker capabilities

3. Verify worker registration:
   ```bash
   curl http://localhost:8000/v1/opencode/workers
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
