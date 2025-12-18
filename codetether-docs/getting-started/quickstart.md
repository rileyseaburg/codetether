---
title: Quick Start
description: Get CodeTether running and send your first agent task in 5 minutes
---

# Quick Start

Get CodeTether Server running and send your first task in 5 minutes.

## Prerequisites

- Python 3.10+ installed
- `pip` package manager

## Step 1: Install CodeTether

```bash
pip install codetether
```

## Step 2: Start the Server

```bash
codetether serve --port 8000
```

You should see:

```
INFO:     CodeTether Server starting...
INFO:     A2A JSON-RPC endpoint: http://0.0.0.0:8000/v1/a2a (alias: /)
INFO:     Agent Card: http://0.0.0.0:8000/.well-known/agent-card.json
INFO:     Monitor UI: http://0.0.0.0:8000/v1/monitor/
INFO:     Uvicorn running on http://0.0.0.0:8000
```

## Step 3: Discover the Agent

Every A2A-compliant agent exposes an Agent Card at `/.well-known/agent-card.json`:

```bash
curl http://localhost:8000/.well-known/agent-card.json | jq
```

```json
{
  "name": "CodeTether Server",
  "description": "Production A2A coordination server",
  "url": "http://localhost:8000",
  "version": "1.0.0",
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
    }
  ]
}
```

## Step 4: Send a Task

Send your first task using the A2A JSON-RPC protocol:

```bash
curl -X POST http://localhost:8000/v1/a2a \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "message/send",
    "params": {
      "message": {
        "parts": [{"type": "text", "content": "Hello, CodeTether!"}]
      }
    },
    "id": "task-001"
  }'
```

Response:

```json
{
  "jsonrpc": "2.0",
  "result": {
    "task": {
      "id": "task-abc123",
      "status": "completed"
    },
    "message": {
      "parts": [
        {"type": "text", "content": "Hello! I'm CodeTether Server, ready to coordinate your agents."}
      ]
    }
  },
  "id": "task-001"
}
```

## Step 5: Open the Monitor UI

Open your browser to [http://localhost:8000/v1/monitor/](http://localhost:8000/v1/monitor/) to see:

- Connected agents
- Active tasks
- Real-time message streams
- System health

## Step 6: Scale with Distributed Workers

CodeTether is designed to scale. You can run **Distributed Workers** on any machine to execute tasks:

1.  **Install the worker** on a remote machine:
    ```bash
    git clone https://github.com/rileyseaburg/codetether.git
    cd codetether && sudo ./agent_worker/install.sh
    ```
2.  **Configure** the worker to point to your server.
3.  **Deploy Anywhere**: Whether it's a local VM, a cloud instance, or a Kubernetes cluster, CodeTether workers can run anywhere they have outbound access to the server.

Learn more in the [Distributed Workers Guide](../features/distributed-workers.md) and our [Deployment Options](../deployment/docker.md).

## Using the Python Client

Install the client library:

```bash
pip install codetether
```

```python
from a2a_server import A2AClient

# Connect to the server
client = A2AClient("http://localhost:8000")

# Send a task
result = client.send_task("Analyze this code for security issues")
print(result.artifacts[0].text)

# Stream responses
for chunk in client.send_task_streaming("Generate a report"):
    print(chunk, end="", flush=True)
```

## Using with OpenCode

If you have built [OpenCode from the local fork](../features/opencode.md) (included in the `opencode/` directory), you can register codebases:

```bash
# Register a codebase
curl -X POST http://localhost:8000/v1/opencode/codebases \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-project",
    "path": "/home/user/projects/my-project",
    "description": "My awesome project"
  }'

# Trigger an agent task
curl -X POST http://localhost:8000/v1/opencode/codebases/{codebase_id}/trigger \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Add unit tests for the authentication module",
    "agent": "build"
  }'
```

## What's Next?

<div class="grid cards" markdown>

-   :material-cog:{ .lg .middle } __Configure the Server__

    Set up Redis, authentication, and more

    [:octicons-arrow-right-24: Configuration](configuration.md)

-   :material-code-braces:{ .lg .middle } __OpenCode Integration__

    Bridge AI coding agents to your codebase

    [:octicons-arrow-right-24: OpenCode](../features/opencode.md)

-   :material-kubernetes:{ .lg .middle } __Deploy to Production__

    Kubernetes, Helm charts, and scaling

    [:octicons-arrow-right-24: Deployment](../deployment/docker.md)

-   :material-api:{ .lg .middle } __API Reference__

    Full endpoint documentation

    [:octicons-arrow-right-24: API Docs](../api/overview.md)

</div>
