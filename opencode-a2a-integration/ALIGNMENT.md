# A2A Server Alignment

## Overview

This repository contains the A2A (Agent-to-Agent) Server infrastructure for managing distributed AI agent workflows. It integrates with OpenCode to provide a complete agent orchestration platform.

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Marketing     │     │    A2A Server   │     │  OpenCode       │
│   Web UI        │────▶│    (Python)     │◀────│  Worker         │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌─────────────────┐
                        │   iOS App       │
                        │  (A2AMonitor)   │
                        └─────────────────┘
```

## Key Components

### A2A Server (`a2a_server/`)

- **monitor_api.py** - REST API for monitoring, codebases, tasks, sessions
- **worker_sse.py** - SSE streaming for worker task distribution
- **task_manager.py** - Task queue and lifecycle management

### OpenCode Integration (`opencode-a2a-integration/`)

- **a2a.ts** - CLI command: `opencode a2a --server <url>`
- **a2a/client.ts** - HTTP client for A2A server communication
- **a2a/notify.ts** - Notifications to iOS app via monitor/intervene
- **a2a/vault.ts** - HashiCorp Vault for secrets (SendGrid, etc.)
- **harness.ts** - Repo-specific workflow enforcement

### iOS App (`ui/swift/A2AMonitor/`)

- Real-time monitoring via SSE
- Local notifications for agent messages
- Task management and session viewing

### Marketing Site (`marketing-site/`)

- Dashboard for codebase management
- Agent triggering and monitoring
- Session history and output viewing

## Task Flow

1. **User triggers agent** via Marketing Site or iOS App
2. **Task created** with `status: pending` in A2A Server
3. **Worker receives task** via SSE stream (`/v1/worker/tasks/stream`)
4. **Worker claims task** atomically (`POST /v1/worker/tasks/claim`)
5. **Worker executes** using OpenCode session system
6. **Progress reported** via `/v1/monitor/intervene` (shows in iOS app)
7. **Task released** with result (`POST /v1/worker/tasks/release`)

## Notifications

The OpenCode worker sends notifications to:

- **iOS App** - Via `/v1/monitor/intervene` endpoint, received via SSE
- **Email** - Via SendGrid (if `--email` and `--sendgrid-key` provided)
- **Push** - Via custom endpoint (if `--push-url` provided)

Events:

- `worker_started` - Worker connected to server
- `worker_stopped` - Worker disconnected (SIGINT/SIGTERM)
- `task_started` - Task claimed and execution beginning
- `task_completed` - Task finished successfully
- `task_failed` - Task failed with error

## Harness System

The harness provides repo-specific workflow enforcement:

### Spotless Bin Co

- Must use RustyRoad MCP tools for database operations
- Must use spotless-ads MCP tools for campaigns
- Funnel operations via component system
- Template operations via Tera macros

### RouteFunnels

- Similar funnel/template workflow enforcement
- Database operations via RustyRoad tools

## Environment Variables

```bash
# A2A Server
A2A_HOST=0.0.0.0
A2A_PORT=8000
A2A_AUTH_TOKENS=agent1:secret123,agent2:secret456

# OpenCode Worker
SENDGRID_API_KEY=SG.xxx
VAULT_ADDR=http://vault:8200
VAULT_TOKEN=hvs.xxx
```

## Running the Worker

```bash
# Basic
opencode a2a --server https://a2a.example.com --token secret123 --name my-worker

# With email notifications
opencode a2a -s https://a2a.example.com -t secret123 -n my-worker \
  --email riley@spotlessbinco.com --sendgrid-key SG.xxx

# With auto-approve all tools
opencode a2a -s https://a2a.example.com -t secret123 -n my-worker --auto-approve all
```

## Development

```bash
# Start A2A server
cd /home/riley/A2A-Server-MCP
source .venv/bin/activate
python run_server.py run

# Start OpenCode worker (from opencode repo)
cd opencode/packages/opencode
bun dev a2a -s http://localhost:8000 -t secret123 -n dev-worker --auto-approve all
```

## TODO

- [ ] APNs push notifications for iOS (currently uses local notifications via SSE)
- [ ] Worker health monitoring and auto-restart
- [ ] Task priority queue
- [ ] Multi-codebase worker support
- [ ] Metrics and observability
