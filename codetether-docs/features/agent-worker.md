---
title: Agent Worker
description: Deploy autonomous AI agents on remote machines with the Agent Worker daemon
---

# Agent Worker

The **Agent Worker** is a standalone daemon that runs on machines with codebases, connecting to a CodeTether server to receive and execute AI agent tasks. It enables distributed, autonomous code execution across your infrastructure.

!!! success "Zero-Touch Automation"
    Once configured, the Agent Worker autonomously pulls tasks from the server, executes them using OpenCode, and reports results—all without human intervention.

## Overview

The Agent Worker provides:

- **Remote Task Execution**: Run AI agents on machines where codebases live
- **Codebase Registration**: Automatically register local codebases with the server
- **Session Sync**: Report OpenCode session history to the central server
- **Output Streaming**: Real-time task output streaming to the server
- **Graceful Lifecycle**: Proper shutdown handling and resource cleanup
- **Systemd Integration**: Run as a production-grade Linux service

```mermaid
sequenceDiagram
    participant Server as CodeTether Server
    participant Worker as Agent Worker
    participant OpenCode as OpenCode CLI
    participant Codebase as Local Codebase

    Worker->>Server: Register worker
    Worker->>Server: Register codebases

    loop Poll Interval
        Worker->>Server: Get pending tasks
        Server-->>Worker: Task list
        Worker->>OpenCode: Execute task
        OpenCode->>Codebase: Read/modify files
        Worker->>Server: Stream output
        Worker->>Server: Report completion
    end

    loop Session Sync
        Worker->>Server: Sync OpenCode sessions
    end
```

## Architecture

The Agent Worker acts as a bridge between the CodeTether server and local codebases:

```
┌─────────────────────────────────────────────────────────────┐
│                    Remote Machine                            │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Agent Worker Daemon                     │    │
│  │  ┌─────────────┐  ┌──────────────┐  ┌────────────┐  │    │
│  │  │   Poller    │  │  Executor    │  │  Reporter  │  │    │
│  │  │  (tasks)    │  │  (opencode)  │  │  (output)  │  │    │
│  │  └──────┬──────┘  └──────┬───────┘  └─────┬──────┘  │    │
│  │         │                │                │         │    │
│  │         └────────────────┼────────────────┘         │    │
│  │                          │                          │    │
│  └──────────────────────────┼──────────────────────────┘    │
│                             │                               │
│  ┌──────────────────────────┼──────────────────────────┐    │
│  │   /home/user/project-a   │   /home/user/project-b   │    │
│  │        Codebase 1        │        Codebase 2        │    │
│  └──────────────────────────┴──────────────────────────┘    │
│                             │                               │
│                             ▼                               │
│                     OpenCode Binary                         │
│                    ~/.local/bin/opencode                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ HTTPS
                              ▼
                    ┌─────────────────┐
                    │ CodeTether API  │
                    │ api.codetether  │
                    │      .run       │
                    └─────────────────┘
```

### Components

| Component | Purpose |
|-----------|---------|
| **Poller** | Fetches pending tasks from the server at configurable intervals |
| **Executor** | Runs OpenCode agents on local codebases |
| **Reporter** | Streams task output and syncs session history |
| **Lifecycle Manager** | Handles worker registration, signals, and cleanup |

---

## Installation

### Quick Install (Linux)

```bash
# Clone repository (if not already)
git clone https://github.com/rileyseaburg/A2A-Server-MCP.git
cd A2A-Server-MCP

# Run installer as root
sudo ./agent_worker/install.sh
```

The installer:

1. Creates a dedicated `a2a-worker` system user
2. Installs the worker script to `/opt/a2a-worker/`
3. Creates a Python virtual environment with dependencies
4. Installs the systemd service unit
5. Creates configuration directory at `/etc/a2a-worker/`

### Manual Installation

```bash
# Create directories
sudo mkdir -p /opt/a2a-worker /etc/a2a-worker

# Copy worker script
sudo cp agent_worker/worker.py /opt/a2a-worker/
sudo chmod +x /opt/a2a-worker/worker.py

# Create virtual environment
sudo python3 -m venv /opt/a2a-worker/venv
sudo /opt/a2a-worker/venv/bin/pip install aiohttp

# Copy configuration
sudo cp agent_worker/config.example.json /etc/a2a-worker/config.json
sudo chmod 600 /etc/a2a-worker/config.json

# Install systemd service
sudo cp agent_worker/systemd/a2a-agent-worker.service /etc/systemd/system/
sudo systemctl daemon-reload
```

### Requirements

- **Python 3.8+** with `asyncio` and `aiohttp`
- **OpenCode** installed and accessible
- **Network access** to the CodeTether server
- **Read/write access** to configured codebases

---

## Configuration

### Configuration File

The worker reads configuration from `/etc/a2a-worker/config.json`:

```json
{
    "server_url": "https://api.codetether.run",
    "worker_name": "dev-vm-worker",
    "poll_interval": 5,
    "opencode_bin": null,
    "codebases": [
        {
            "name": "my-project",
            "path": "/home/user/my-project",
            "description": "Main application repository"
        },
        {
            "name": "backend-api",
            "path": "/home/user/backend-api",
            "description": "Backend microservices"
        }
    ],
    "capabilities": [
        "opencode",
        "build",
        "deploy",
        "test"
    ]
}
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `server_url` | string | — | **Required.** CodeTether server URL |
| `worker_name` | string | hostname | Human-readable name for the worker |
| `poll_interval` | integer | `5` | Seconds between task polls |
| `opencode_bin` | string | auto-detect | Path to OpenCode binary |
| `codebases` | array | `[]` | List of codebases to register |
| `codebases[].name` | string | directory name | Display name for the codebase |
| `codebases[].path` | string | — | **Required.** Absolute path to codebase |
| `codebases[].description` | string | `""` | Description of the codebase |
| `capabilities` | array | `["opencode", "build", "deploy"]` | Worker capabilities to advertise |

### Environment Variables

Environment variables can override configuration:

```bash
# /etc/a2a-worker/env
A2A_SERVER_URL=https://api.codetether.run
A2A_WORKER_NAME=production-worker-1
A2A_POLL_INTERVAL=10
```

| Variable | Description |
|----------|-------------|
| `A2A_SERVER_URL` | CodeTether server URL |
| `A2A_WORKER_NAME` | Worker identifier |
| `A2A_POLL_INTERVAL` | Poll interval in seconds |

---

## Running the Worker

### Systemd Service (Recommended)

```bash
# Start the service
sudo systemctl start a2a-agent-worker

# Enable on boot
sudo systemctl enable a2a-agent-worker

# Check status
sudo systemctl status a2a-agent-worker

# View logs
sudo journalctl -u a2a-agent-worker -f
```

### Manual Execution

For debugging or testing:

```bash
# Basic usage
python3 agent_worker/worker.py \
    --server https://api.codetether.run \
    --name my-worker

# With config file
python3 agent_worker/worker.py --config /etc/a2a-worker/config.json

# With inline codebase
python3 agent_worker/worker.py \
    --server https://api.codetether.run \
    --codebase my-project:/home/user/my-project \
    --codebase other-project:/home/user/other-project

# Custom poll interval
python3 agent_worker/worker.py \
    --server https://api.codetether.run \
    --poll-interval 10
```

### Command-Line Options

| Flag | Short | Description |
|------|-------|-------------|
| `--server` | `-s` | Server URL |
| `--name` | `-n` | Worker name |
| `--config` | `-c` | Path to config file |
| `--codebase` | `-b` | Codebase to register (format: `name:path` or just `path`) |
| `--poll-interval` | `-i` | Poll interval in seconds |
| `--opencode` | — | Path to OpenCode binary |

---

## How It Works

### 1. Worker Registration

On startup, the worker registers itself with the server:

```http
POST /v1/opencode/workers/register
{
    "worker_id": "abc123",
    "name": "dev-vm-worker",
    "capabilities": ["opencode", "build", "deploy"],
    "hostname": "dev-vm.internal"
}
```

### 2. Codebase Registration

Each configured codebase is registered:

```http
POST /v1/opencode/codebases
{
    "name": "my-project",
    "path": "/home/user/my-project",
    "description": "Main application",
    "worker_id": "abc123"
}
```

!!! info "Worker Affinity"
    Tasks for a codebase are routed only to the worker that registered it. This ensures tasks execute where the code actually lives.

### 3. Task Polling

The worker polls for pending tasks:

```http
GET /v1/opencode/tasks?status=pending&worker_id=abc123
```

Only tasks assigned to this worker's codebases are returned.

### 4. Task Execution

When a task is received:

1. **Claim**: Worker marks task as `running`
2. **Execute**: Runs OpenCode with the task prompt
3. **Stream**: Output is streamed to the server in real-time
4. **Report**: Final status (`completed` or `failed`) is reported

```bash
# Equivalent OpenCode command
opencode run --agent build --format json "Add unit tests for auth module"
```

### 5. Session Sync

Every ~60 seconds, the worker syncs OpenCode session history:

```http
POST /v1/opencode/codebases/{id}/sessions/sync
{
    "worker_id": "abc123",
    "sessions": [
        {
            "id": "sess_xyz",
            "title": "Added unit tests",
            "created_at": "2025-12-10T15:00:00Z"
        }
    ]
}
```

---

## Task Workflow

### Creating a Task

Tasks can be created via the API:

```bash
curl -X POST https://api.codetether.run/v1/opencode/codebases/cb_abc/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Add authentication",
    "prompt": "Implement JWT authentication for the API endpoints",
    "agent_type": "build",
    "metadata": {
        "model": "anthropic/claude-sonnet-4-20250514"
    }
}'
```

### Task Lifecycle

```
pending → running → completed
              ↓
            failed
```

| Status | Description |
|--------|-------------|
| `pending` | Waiting for a worker to pick up |
| `running` | Currently being executed |
| `completed` | Successfully finished |
| `failed` | Execution error occurred |

### Resuming Sessions

Tasks can resume existing OpenCode sessions:

```json
{
    "title": "Continue refactoring",
    "prompt": "Continue the database refactoring from where we left off",
    "metadata": {
        "resume_session_id": "sess_xyz789"
    }
}
```

---

## Security

### Systemd Hardening

The provided service unit includes security hardening:

```ini
[Service]
# Run as dedicated user
User=a2a-worker
Group=a2a-worker

# Security restrictions
NoNewPrivileges=true
ProtectSystem=full
ProtectHome=read-only
ReadWritePaths=/home /opt/a2a-worker
PrivateTmp=true

# Resource limits
MemoryMax=2G
CPUQuota=200%
```

### File Permissions

```bash
# Configuration is readable only by root/worker
sudo chmod 600 /etc/a2a-worker/config.json
sudo chown a2a-worker:a2a-worker /etc/a2a-worker/config.json
```

### Network Security

- Use HTTPS for all server communication
- Consider VPN or private network for internal deployments
- Use authentication tokens when available

---

## Monitoring

### Logs

```bash
# Live logs
sudo journalctl -u a2a-agent-worker -f

# Recent logs
sudo journalctl -u a2a-agent-worker -n 100

# Since last boot
sudo journalctl -u a2a-agent-worker -b
```

### Health Checks

```bash
# Service status
sudo systemctl status a2a-agent-worker

# Process check
pgrep -f "worker.py" && echo "Running" || echo "Not running"
```

### Server-Side Monitoring

Check worker status from the server:

```bash
curl https://api.codetether.run/v1/monitor/workers
```

```json
{
    "workers": [
        {
            "id": "abc123",
            "name": "dev-vm-worker",
            "status": "active",
            "last_heartbeat": "2025-12-10T15:30:00Z",
            "codebases": 2,
            "tasks_completed": 42
        }
    ]
}
```

---

## Troubleshooting

### Worker Not Starting

```bash
# Check logs
sudo journalctl -u a2a-agent-worker -n 50

# Common issues:
# - Python environment not created
# - aiohttp not installed
# - Config file missing or invalid
```

### Cannot Connect to Server

```bash
# Test connectivity
curl -I https://api.codetether.run/v1/opencode/status

# Check DNS resolution
nslookup api.codetether.run

# Check firewall
sudo iptables -L -n | grep 443
```

### OpenCode Not Found

```bash
# Check OpenCode location
which opencode
ls -la ~/.local/bin/opencode

# Verify it works
opencode --version

# Set explicit path in config
{
    "opencode_bin": "/home/user/.local/bin/opencode"
}
```

### Codebase Not Registering

```bash
# Verify path exists
ls -la /home/user/my-project

# Check worker user has access
sudo -u a2a-worker ls /home/user/my-project

# Add worker to user's group
sudo usermod -a -G $USER a2a-worker
```

### Tasks Not Executing

```bash
# Check task queue on server
curl https://api.codetether.run/v1/opencode/tasks?status=pending

# Verify codebase is registered with worker_id
curl https://api.codetether.run/v1/opencode/codebases

# Check worker is polling (in logs)
sudo journalctl -u a2a-agent-worker | grep "poll"
```

---

## Advanced Configuration

### Multiple Workers

Run multiple workers for different codebase sets:

```bash
# Worker 1 - Production codebases
python3 worker.py --name prod-worker --config /etc/a2a-worker/prod.json

# Worker 2 - Development codebases
python3 worker.py --name dev-worker --config /etc/a2a-worker/dev.json
```

### Custom Capabilities

Advertise specific capabilities:

```json
{
    "capabilities": [
        "opencode",
        "python",
        "typescript",
        "docker",
        "kubernetes"
    ]
}
```

### OpenCode Model Selection

Tasks can specify which model to use:

```json
{
    "prompt": "Refactor the database module",
    "metadata": {
        "model": "anthropic/claude-sonnet-4-20250514"
    }
}
```

Supported models:

- `anthropic/claude-sonnet-4-20250514`
- `anthropic/claude-opus-4-20250514`
- `openai/gpt-4o`
- `google/gemini-2.0-flash`
- And many more (see [Models API](../api/opencode.md#list-available-models))

---

## File Reference

### worker.py

Location: `/opt/a2a-worker/worker.py` (installed) or `agent_worker/worker.py` (source)

Main worker script containing:

- `WorkerConfig` - Configuration dataclass
- `LocalCodebase` - Registered codebase dataclass
- `AgentWorker` - Main worker class
- Task polling, execution, and reporting logic
- OpenCode session discovery and sync

### config.example.json

Location: `agent_worker/config.example.json`

Example configuration file to copy and customize.

### install.sh

Location: `agent_worker/install.sh`

Installation script that sets up the worker as a systemd service.

### a2a-agent-worker.service

Location: `agent_worker/systemd/a2a-agent-worker.service`

Systemd service unit with security hardening and resource limits.

---

## Next Steps

- [OpenCode Integration](opencode.md) - Learn about OpenCode features
- [Distributed Workers](distributed-workers.md) - Scale workers horizontally
- [OpenCode API](../api/opencode.md) - Full API reference
- [Production Deployment](../deployment/production.md) - Production checklist
