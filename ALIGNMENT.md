# A2A Server - Master Alignment Document

## CRITICAL: Read This First

This document is the single source of truth for all agents working in this repository. If you are confused about architecture, workflows, or how components connect - this is your guide.

## Repository Structure

```
A2A-Server-MCP/
├── a2a_server/           # Python FastAPI server (the brain)
├── agent_worker/         # Python worker that picks up tasks (PRODUCTION)
├── opencode/             # OpenCode fork (git submodule - DO NOT MODIFY HERE)
├── opencode-a2a-integration/  # TypeScript integration for OpenCode CLI
├── marketing-site/       # Next.js web dashboard
├── ui/swift/A2AMonitor/  # iOS monitoring app
└── agents/               # Agent definitions and configs
```

## The Two Workers - UNDERSTAND THIS

### 1. Python Worker (`agent_worker/worker.py`) - PRODUCTION

- Runs as systemd service at `/opt/a2a-worker/`
- Config at `/etc/a2a-worker/config.json`
- Connects to A2A server via SSE
- Spawns OpenCode processes to execute tasks
- THIS IS WHAT RUNS IN PRODUCTION

### 2. TypeScript Worker (`opencode-a2a-integration/`) - CLI TOOL

- For running `opencode a2a --server <url>` command
- Integrated into OpenCode binary
- Used for development/testing
- NOT the production worker

**THEY ARE NOT THE SAME. The Python worker calls the OpenCode binary as a subprocess.**

## Task Flow (How Work Gets Done)

```
1. User triggers task (Web UI / iOS App / API)
         │
         ▼
2. A2A Server creates task (status: pending)
         │
         ▼
3. Worker receives via SSE (/v1/worker/tasks/stream)
         │
         ▼
4. Worker claims task (POST /v1/worker/tasks/claim)
         │
         ▼
5. Worker spawns: opencode run --agent build --format json -- "<prompt>"
         │
         ▼
6. OpenCode executes, worker streams output
         │
         ▼
7. Worker releases task (POST /v1/worker/tasks/release)
         │
         ▼
8. Notification sent (monitor/intervene → iOS app via SSE)
```

## API Endpoints You Need to Know

### Task Management

- `GET /v1/opencode/tasks` - List all tasks
- `POST /v1/opencode/codebases/{id}/tasks` - Create task
- `POST /v1/opencode/tasks/{id}/cancel` - Cancel task

### Worker Communication

- `GET /v1/worker/tasks/stream` - SSE stream for task events
- `POST /v1/worker/tasks/claim` - Claim a task atomically
- `POST /v1/worker/tasks/release` - Release task with result

### Notifications (iOS App)

- `POST /v1/monitor/intervene` - Send message that appears in iOS app
- `GET /v1/monitor/stream` - SSE stream iOS app listens to

## Codebase Management

### Spotless Bin Co (`/home/riley/spotlessbinco`)

- Use RustyRoad MCP tools for database
- Use spotless-ads MCP tools for campaigns
- Follow funnel component architecture
- Templates use Tera macros

### RouteFunnels

- Similar patterns to Spotless Bin Co
- Funnel hierarchy: landing → checkout → upsell → downsell → thankyou

## MCP Tools Available

When working in Spotless Bin Co repos, these MCP tools are available:

### Database (RustyRoad)

- `rustyroad_rustyroad_schema` - View schema
- `rustyroad_rustyroad_query` - Execute SQL
- `rustyroad_rustyroad_migrate` - Run migrations
- `rustyroad_rustyroad_migration_generate` - Create migrations

### Ads (spotless-ads)

- `spotless-ads_list_targeting_zones` - Get zones FIRST
- `spotless-ads_list_funnels` - Get funnels
- `spotless-ads_ai_create_bulk_ads` - Create ads with AI

### A2A Server

- `a2a-server_create_task` - Create tasks
- `a2a-server_list_tasks` - List tasks
- `a2a-server_send_message` - Send messages

## Notifications

### How to Send Notifications

The worker sends notifications via `/v1/monitor/intervene`:

```json
POST /v1/monitor/intervene
{
  "agent_id": "worker-name",
  "message": "[TASK_COMPLETED] Task finished successfully",
  "timestamp": "2026-01-11T02:30:00Z"
}
```

This appears in:

1. iOS App (via SSE to `/v1/monitor/stream`)
2. Web UI monitor page
3. Logs

### Email Notifications

Set `SENDGRID_API_KEY` environment variable. The TypeScript integration supports:

```bash
opencode a2a --email riley@spotlessbinco.com --sendgrid-key SG.xxx
```

### Email Replies (Task Continuation)

Users can **reply directly to notification emails** to continue a conversation with the worker.

**How it works:**
1. Worker sends email with `reply-to: task+{session_id}@inbound.codetether.run`
2. User replies to the email
3. SendGrid Inbound Parse forwards to `/v1/email/inbound`
4. Server creates continuation task with `resume_session_id`
5. Worker picks up task and resumes the OpenCode session

**Configuration:**
```json
{
    "email_inbound_domain": "inbound.codetether.run",
    "email_reply_prefix": "task"
}
```

Or environment variables:
```bash
EMAIL_INBOUND_DOMAIN=inbound.codetether.run
EMAIL_REPLY_PREFIX=task
```

## Configuration Files

### Worker Config (`/etc/a2a-worker/config.json`)

```json
{
    "server_url": "https://api.codetether.run",
    "worker_name": "spotless-dev-worker",
    "opencode_bin": "/opt/a2a-worker/bin/opencode",
    "codebases": [
        { "name": "spotlessbinco", "path": "/home/riley/spotlessbinco" }
    ],
    "sendgrid_api_key": "SG.xxx",
    "sendgrid_from_email": "noreply@codetether.run",
    "notification_email": "you@example.com",
    "email_inbound_domain": "inbound.codetether.run"
}
```

### A2A Server (`.env`)

```bash
A2A_HOST=0.0.0.0
A2A_PORT=8000
A2A_AUTH_TOKENS=agent1:secret123
```

## Codebase Routing - CRITICAL

Workers **must** register their codebases to receive tasks for them. The server routes tasks based on the `codebase_id` field:

- **Specific codebase tasks** (e.g., `codebase_id: "abc123"`): Only sent to workers that have registered that specific codebase ID
- **Global tasks** (`codebase_id: "global"`): Sent to any worker
- **Pending registration tasks** (`codebase_id: "__pending__"`): Sent to any worker (for codebase discovery)

**IMPORTANT**: Workers with **no registered codebases** will only receive `global` and `__pending__` tasks. This prevents cross-server task leakage where a worker picks up work for codebases it doesn't have access to.

### How Workers Register Codebases

1. Worker connects via SSE with `X-Codebases` header containing comma-separated codebase IDs
2. Worker calls `PUT /v1/worker/codebases` to update its codebase list
3. Worker registers codebases via `POST /v1/opencode/codebases` which associates them with its worker_id

## Common Mistakes - AVOID THESE

1. **Modifying opencode/ directly** - It's a submodule. Changes go in `opencode-a2a-integration/`
2. **Confusing the two workers** - Python worker is production, TypeScript is CLI tool
3. **Not using MCP tools** - Always use spotless-ads/rustyroad tools, not manual file edits
4. **Posting to wrong endpoint** - Use `/v1/monitor/intervene` for notifications, not `/v1/monitor/messages`
5. **Missing timestamp** - The intervene endpoint requires `agent_id`, `message`, AND `timestamp`
6. **Assuming empty codebases means "accept all"** - Workers must explicitly register codebases to receive codebase-specific tasks

## Running Locally

### Start A2A Server

```bash
cd /home/riley/A2A-Server-MCP
source .venv/bin/activate
python run_server.py run
```

### Start Worker (Development)

```bash
# Using TypeScript CLI
opencode a2a -s http://localhost:8000 -t secret123 -n dev-worker --auto-approve all

# Or using Python worker
python agent_worker/worker.py
```

### Check Health

```bash
curl http://localhost:8000/health
```

## Debugging

### Check if worker is connected

```bash
curl http://localhost:8000/v1/opencode/workers
```

### Check pending tasks

```bash
curl http://localhost:8000/v1/opencode/tasks?status=pending
```

### Check monitor messages

```bash
curl http://localhost:8000/v1/monitor/messages?limit=10
```

### Worker logs

```bash
journalctl -u a2a-worker -f  # If running as service
tail -f /tmp/a2a-worker.log  # If running manually
```

## Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                           CLIENTS                                     │
├──────────────┬──────────────┬──────────────┬────────────────────────┤
│  Marketing   │   iOS App    │  OpenCode    │   Direct API           │
│  Web UI      │  A2AMonitor  │  CLI         │   Calls                │
└──────┬───────┴──────┬───────┴──────┬───────┴──────┬─────────────────┘
       │              │              │              │
       └──────────────┴──────────────┴──────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      A2A SERVER (Python FastAPI)                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │ monitor_api │  │ worker_sse  │  │ task_manager│  │ auth        │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │
└──────────────────────────────┬───────────────────────────────────────┘
                               │
                               ▼ SSE
┌──────────────────────────────────────────────────────────────────────┐
│                      PYTHON WORKER (agent_worker/)                    │
│  - Receives tasks via SSE                                            │
│  - Spawns OpenCode processes                                         │
│  - Reports results back to server                                    │
│  - Sends notifications                                               │
└──────────────────────────────┬───────────────────────────────────────┘
                               │
                               ▼ subprocess
┌──────────────────────────────────────────────────────────────────────┐
│                      OPENCODE (opencode run ...)                      │
│  - Executes prompts                                                  │
│  - Uses MCP tools (rustyroad, spotless-ads, etc.)                   │
│  - Returns JSON output                                               │
└──────────────────────────────────────────────────────────────────────┘
```

## Questions?

If you're still confused:

1. Re-read the "Two Workers" section
2. Check the task flow diagram
3. Look at `/v1/opencode/tasks` to see actual task data
4. Check `/v1/monitor/messages` for recent activity

**Remember: The Python worker is the orchestrator. OpenCode is the executor.**
