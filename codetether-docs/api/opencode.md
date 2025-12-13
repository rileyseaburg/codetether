---
title: OpenCode API
description: API reference for OpenCode integration - codebases, sessions, and AI coding agents
---

# OpenCode API

The OpenCode API provides integration with AI coding agents. It manages codebases, sessions, tasks, and real-time agent interactions.

!!! info "Base URL"
    All OpenCode endpoints are prefixed with `/v1/opencode`
    ```
    https://codetether.example.com/v1/opencode/...
    ```

## Status

### Check OpenCode Status

Check if the OpenCode bridge is available and initialized. Includes local runtime session information.

```http
GET /v1/opencode/status
```

**Response**

```json
{
  "available": true,
  "message": "OpenCode integration ready",
  "opencode_binary": "/usr/local/bin/opencode",
  "registered_codebases": 3,
  "auto_start": true,
  "runtime": {
    "available": true,
    "storage_path": "/home/user/.local/share/opencode/storage",
    "projects": 3,
    "sessions": 247
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `available` | boolean | Whether OpenCode bridge is initialized |
| `message` | string | Human-readable status message |
| `opencode_binary` | string | Path to OpenCode executable |
| `registered_codebases` | integer | Number of registered codebases |
| `auto_start` | boolean | Whether agents auto-start on trigger |
| `runtime` | object | Local runtime session information (if available) |
| `runtime.available` | boolean | Whether local OpenCode storage is detected |
| `runtime.storage_path` | string | Path to OpenCode storage directory |
| `runtime.projects` | integer | Number of local projects |
| `runtime.sessions` | integer | Total number of local sessions |

---

## Models

### List Available Models

Get a list of AI models available for agent tasks.

```http
GET /v1/opencode/models
```

**Response**

```json
[
  {
    "id": "anthropic/claude-sonnet-4-20250514",
    "name": "Claude Sonnet 4",
    "provider": "Anthropic"
  },
  {
    "id": "openai/gpt-4o",
    "name": "GPT-4o",
    "provider": "OpenAI"
  },
  {
    "id": "google/gemini-2.0-flash",
    "name": "Gemini 2.0 Flash",
    "provider": "Google"
  }
]
```

**Available Providers**

- **Anthropic**: Claude Opus, Sonnet, Haiku models
- **OpenAI**: GPT-4o, o1, o3-mini models
- **Google**: Gemini 2.0/2.5 models
- **DeepSeek**: DeepSeek Chat, Reasoner
- **xAI**: Grok 2, Grok 3
- **Azure AI Foundry**: Custom Azure-hosted models

---

## Codebases

### List Codebases

Get all registered codebases.

```http
GET /v1/opencode/codebases
```

**Response**

```json
[
  {
    "id": "cb_abc123",
    "name": "my-project",
    "path": "/home/user/projects/my-project",
    "description": "Main application codebase",
    "worker_id": "worker-1",
    "created_at": "2025-12-10T10:00:00Z"
  }
]
```

---

### Register Codebase

Register a new codebase for agent work.

```http
POST /v1/opencode/codebases
Content-Type: application/json
```

**Request Body**

```json
{
  "name": "my-project",
  "path": "/home/user/projects/my-project",
  "description": "Main application codebase",
  "agent_config": {
    "default_model": "anthropic/claude-sonnet-4-20250514",
    "auto_approve": false
  },
  "worker_id": "worker-1"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | ✅ | Display name for the codebase |
| `path` | string | ✅ | Absolute path to the codebase directory |
| `description` | string | ❌ | Description of the codebase |
| `agent_config` | object | ❌ | Agent configuration overrides |
| `worker_id` | string | ❌ | Associate with specific worker |

**Response**

```json
{
  "success": true,
  "codebase": {
    "id": "cb_abc123",
    "name": "my-project",
    "path": "/home/user/projects/my-project",
    "description": "Main application codebase",
    "created_at": "2025-12-10T10:00:00Z"
  }
}
```

---

### Get Codebase

Get details of a specific codebase.

```http
GET /v1/opencode/codebases/{codebase_id}
```

**Response**

```json
{
  "id": "cb_abc123",
  "name": "my-project",
  "path": "/home/user/projects/my-project",
  "description": "Main application codebase",
  "worker_id": "worker-1",
  "agent_config": {
    "default_model": "anthropic/claude-sonnet-4-20250514"
  },
  "created_at": "2025-12-10T10:00:00Z",
  "last_activity": "2025-12-10T15:30:00Z"
}
```

---

### Delete Codebase

Unregister a codebase.

```http
DELETE /v1/opencode/codebases/{codebase_id}
```

**Response**

```json
{
  "success": true,
  "message": "Codebase cb_abc123 deleted"
}
```

---

## Agent Actions

### Trigger Agent

Start an AI agent on a codebase with a prompt.

```http
POST /v1/opencode/codebases/{codebase_id}/trigger
Content-Type: application/json
```

**Request Body**

```json
{
  "prompt": "Add comprehensive unit tests for the authentication module",
  "agent": "build",
  "model": "anthropic/claude-sonnet-4-20250514",
  "files": ["src/auth/login.py", "src/auth/oauth.py"],
  "metadata": {
    "priority": "high",
    "ticket": "JIRA-123"
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `prompt` | string | ✅ | The task instruction for the agent |
| `agent` | string | ❌ | Agent type: `build`, `plan`, `explore`, `general` (default: `build`) |
| `model` | string | ❌ | Model to use (default: codebase config or Claude Sonnet) |
| `files` | array | ❌ | Specific files to focus on |
| `metadata` | object | ❌ | Custom metadata to attach to the task |

**Response**

```json
{
  "success": true,
  "session_id": "sess_xyz789",
  "task_id": "task_abc123",
  "status": "running",
  "message": "Agent started on codebase my-project"
}
```

---

### Send Message

Send a follow-up message to a running agent session.

```http
POST /v1/opencode/codebases/{codebase_id}/message
Content-Type: application/json
```

**Request Body**

```json
{
  "message": "Also add integration tests for the OAuth flow",
  "agent": "build"
}
```

**Response**

```json
{
  "success": true,
  "message": "Message sent to agent"
}
```

---

### Interrupt Agent

Send an interrupt signal to pause the agent.

```http
POST /v1/opencode/codebases/{codebase_id}/interrupt
```

**Response**

```json
{
  "success": true,
  "message": "Interrupt signal sent"
}
```

---

### Stop Agent

Stop the running agent completely.

```http
POST /v1/opencode/codebases/{codebase_id}/stop
```

**Response**

```json
{
  "success": true,
  "message": "Agent stopped"
}
```

---

### Get Agent Status

Check the current status of an agent on a codebase.

```http
GET /v1/opencode/codebases/{codebase_id}/status
```

**Response**

```json
{
  "codebase_id": "cb_abc123",
  "status": "running",
  "session_id": "sess_xyz789",
  "current_task": "Adding unit tests",
  "started_at": "2025-12-10T15:30:00Z",
  "model": "anthropic/claude-sonnet-4-20250514"
}
```

---

## Sessions

### List Sessions

Get session history for a codebase.

```http
GET /v1/opencode/codebases/{codebase_id}/sessions
```

**Query Parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| `limit` | integer | Maximum sessions to return (default: 50) |
| `offset` | integer | Pagination offset |

**Response**

```json
{
  "sessions": [
    {
      "id": "sess_xyz789",
      "codebase_id": "cb_abc123",
      "started_at": "2025-12-10T15:30:00Z",
      "ended_at": "2025-12-10T16:45:00Z",
      "status": "completed",
      "model": "anthropic/claude-sonnet-4-20250514",
      "prompt": "Add unit tests for authentication",
      "messages_count": 24
    }
  ],
  "total": 15,
  "limit": 50,
  "offset": 0
}
```

---

### Sync Sessions

Sync sessions from OpenCode to the server database.

```http
POST /v1/opencode/codebases/{codebase_id}/sessions/sync
```

**Response**

```json
{
  "success": true,
  "synced": 5,
  "message": "Synced 5 sessions from OpenCode"
}
```

---

### Get Session Messages

Get all messages from a specific session.

```http
GET /v1/opencode/codebases/{codebase_id}/messages?session_id={session_id}
```

**Response**

```json
{
  "messages": [
    {
      "id": "msg_001",
      "role": "user",
      "content": "Add unit tests for authentication",
      "timestamp": "2025-12-10T15:30:00Z"
    },
    {
      "id": "msg_002",
      "role": "assistant",
      "content": "I'll analyze the authentication module and create comprehensive tests...",
      "timestamp": "2025-12-10T15:30:05Z"
    }
  ]
}
```

---

## Tasks

### Create Task

Create a queued task for an agent to pick up.

```http
POST /v1/opencode/codebases/{codebase_id}/tasks
Content-Type: application/json
```

**Request Body**

```json
{
  "title": "Add unit tests",
  "prompt": "Add comprehensive unit tests for the authentication module",
  "agent_type": "build",
  "priority": 1,
  "metadata": {
    "ticket": "JIRA-123"
  }
}
```

**Response**

```json
{
  "success": true,
  "task": {
    "id": "task_abc123",
    "codebase_id": "cb_abc123",
    "title": "Add unit tests",
    "status": "pending",
    "priority": 1,
    "created_at": "2025-12-10T15:30:00Z"
  }
}
```

---

### List Tasks

Get all tasks, optionally filtered.

```http
GET /v1/opencode/tasks
GET /v1/opencode/codebases/{codebase_id}/tasks
```

**Query Parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | Filter by status: `pending`, `running`, `completed`, `failed` |
| `limit` | integer | Maximum tasks to return |

**Response**

```json
{
  "tasks": [
    {
      "id": "task_abc123",
      "codebase_id": "cb_abc123",
      "title": "Add unit tests",
      "status": "completed",
      "created_at": "2025-12-10T15:30:00Z",
      "completed_at": "2025-12-10T16:45:00Z"
    }
  ]
}
```

---

### Get Task

Get details of a specific task.

```http
GET /v1/opencode/tasks/{task_id}
```

**Response**

```json
{
  "id": "task_abc123",
  "codebase_id": "cb_abc123",
  "title": "Add unit tests",
  "prompt": "Add comprehensive unit tests...",
  "agent_type": "build",
  "status": "running",
  "priority": 1,
  "session_id": "sess_xyz789",
  "created_at": "2025-12-10T15:30:00Z",
  "started_at": "2025-12-10T15:30:05Z"
}
```

---

### Cancel Task

Cancel a pending or running task.

```http
POST /v1/opencode/tasks/{task_id}/cancel
```

**Response**

```json
{
  "success": true,
  "message": "Task cancelled"
}
```

---

## Real-time Events

### Stream Agent Events

Subscribe to real-time events from an agent session via Server-Sent Events (SSE).

```http
GET /v1/opencode/codebases/{codebase_id}/events
Accept: text/event-stream
```

**Event Types**

```
event: status
data: {"status": "running", "message": "Agent started"}

event: output
data: {"type": "text", "content": "Analyzing codebase structure..."}

event: tool_use
data: {"tool": "read_file", "args": {"path": "src/auth/login.py"}}

event: file_change
data: {"action": "create", "path": "tests/test_auth.py"}

event: complete
data: {"status": "completed", "summary": "Added 15 unit tests"}

event: error
data: {"error": "Model rate limit exceeded", "code": "RATE_LIMITED"}
```

**Example Client (JavaScript)**

```javascript
const events = new EventSource('/v1/opencode/codebases/cb_abc123/events');

events.addEventListener('output', (e) => {
  const data = JSON.parse(e.data);
  console.log(data.content);
});

events.addEventListener('complete', (e) => {
  console.log('Agent completed!');
  events.close();
});

events.addEventListener('error', (e) => {
  console.error('Stream error:', e);
});
```

---

## Runtime Sessions

The Runtime API provides **immediate access** to OpenCode sessions stored locally on the system. Unlike the codebase-based session APIs which require registration, these endpoints read directly from the OpenCode storage directory (`~/.local/share/opencode/storage/`).

!!! tip "Zero Configuration"
    When OpenCode is detected on a system, users can immediately browse and resume their existing sessions without registering codebases first.

### Check Runtime Status

Check if OpenCode runtime storage is available on the local system.

```http
GET /v1/opencode/runtime/status
```

**Response**

```json
{
  "available": true,
  "message": "OpenCode runtime detected",
  "storage_path": "/home/user/.local/share/opencode/storage",
  "projects": 3,
  "sessions": 247
}
```

| Field | Type | Description |
|-------|------|-------------|
| `available` | boolean | Whether local OpenCode storage is detected |
| `message` | string | Human-readable status |
| `storage_path` | string | Path to OpenCode storage directory |
| `projects` | integer | Number of projects found |
| `sessions` | integer | Total number of sessions across all projects |

---

### List Runtime Projects

Get all OpenCode projects detected on the local system.

```http
GET /v1/opencode/runtime/projects
```

**Response**

```json
{
  "projects": [
    {
      "id": "2e35f00d-abc123",
      "worktree": "/home/user/my-project",
      "vcs": "git",
      "vcs_dir": "/home/user/my-project/.git",
      "created_at": 1733859600,
      "updated_at": 1733918400,
      "session_count": 45
    },
    {
      "id": "global",
      "worktree": "/",
      "vcs": null,
      "vcs_dir": null,
      "created_at": 1733800000,
      "updated_at": 1733910000,
      "session_count": 5
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique project identifier (git commit hash or "global") |
| `worktree` | string | Path to the project directory |
| `vcs` | string | Version control system (e.g., "git") |
| `vcs_dir` | string | Path to VCS directory |
| `created_at` | number | Unix timestamp when project was first seen |
| `updated_at` | number | Unix timestamp of last activity |
| `session_count` | integer | Number of sessions for this project |

---

### List Runtime Sessions

Get all sessions with pagination, optionally filtered by project.

```http
GET /v1/opencode/runtime/sessions
GET /v1/opencode/runtime/sessions?project_id={project_id}
GET /v1/opencode/runtime/sessions?limit=20&offset=0
```

**Query Parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `project_id` | string | - | Filter sessions by project ID |
| `limit` | integer | 50 | Maximum sessions to return |
| `offset` | integer | 0 | Pagination offset |

**Response**

```json
{
  "sessions": [
    {
      "id": "sess_abc123",
      "project_id": "2e35f00d-abc123",
      "directory": "/home/user/my-project",
      "title": "Implementing OAuth2 authentication flow",
      "version": "1.0.0",
      "created_at": 1733859600,
      "updated_at": 1733918400,
      "summary": {
        "total_messages": 24,
        "model": "claude-sonnet-4-20250514"
      }
    }
  ],
  "total": 247,
  "limit": 50,
  "offset": 0
}
```

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique session identifier |
| `project_id` | string | Associated project ID |
| `directory` | string | Working directory for the session |
| `title` | string | Session title/description |
| `version` | string | OpenCode version used |
| `created_at` | number | Unix timestamp when session started |
| `updated_at` | number | Unix timestamp of last activity |
| `summary` | object | Session statistics |

---

### Get Runtime Session

Get details for a specific session by ID.

```http
GET /v1/opencode/runtime/sessions/{session_id}
```

**Response**

```json
{
  "session": {
    "id": "sess_abc123",
    "project_id": "2e35f00d-abc123",
    "directory": "/home/user/my-project",
    "title": "Implementing OAuth2 authentication flow",
    "version": "1.0.0",
    "created_at": 1733859600,
    "updated_at": 1733918400,
    "summary": {
      "total_messages": 24,
      "model": "claude-sonnet-4-20250514"
    }
  }
}
```

---

### Get Session Messages

Get the conversation history for a session.

```http
GET /v1/opencode/runtime/sessions/{session_id}/messages
GET /v1/opencode/runtime/sessions/{session_id}/messages?limit=20&offset=0
```

**Query Parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 50 | Maximum messages to return |
| `offset` | integer | 0 | Pagination offset |

**Response**

```json
{
  "messages": [
    {
      "id": "msg_001",
      "session_id": "sess_abc123",
      "role": "user",
      "created_at": 1733859600,
      "model": null,
      "cost": null,
      "tokens": null,
      "tool_calls": []
    },
    {
      "id": "msg_002",
      "session_id": "sess_abc123",
      "role": "assistant",
      "created_at": 1733859605,
      "model": "claude-sonnet-4-20250514",
      "cost": 0.0015,
      "tokens": {"input": 150, "output": 423},
      "tool_calls": ["read_file", "write_file"]
    }
  ],
  "total": 24,
  "limit": 50,
  "offset": 0,
  "session_id": "sess_abc123"
}
```

---

### Get Session Parts

Get message parts (content chunks) for a session.

```http
GET /v1/opencode/runtime/sessions/{session_id}/parts
GET /v1/opencode/runtime/sessions/{session_id}/parts?message_id={message_id}
```

**Query Parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `message_id` | string | - | Filter parts by specific message |
| `limit` | integer | 100 | Maximum parts to return |

**Response**

```json
{
  "parts": [
    {
      "id": "part_001",
      "message_id": "msg_001",
      "type": "text",
      "content": "Please implement OAuth2 authentication...",
      "created_at": 1733859600
    },
    {
      "id": "part_002",
      "message_id": "msg_002",
      "type": "tool_use",
      "tool_name": "read_file",
      "arguments": {"path": "src/auth/oauth.py"},
      "created_at": 1733859605
    }
  ],
  "session_id": "sess_abc123",
  "message_id": null
}
```

---

## Database API

The Database API provides access to PostgreSQL-persisted data for workers, codebases, and sessions. These endpoints return data that survives server restarts and works across multiple replicas.

!!! info "PostgreSQL Required"
    These endpoints require `DATABASE_URL` to be configured. Without PostgreSQL, they return empty results.

### Database Status

Check PostgreSQL connection status and statistics.

```http
GET /v1/opencode/database/status
```

**Response**

```json
{
  "available": true,
  "message": "PostgreSQL connected",
  "stats": {
    "workers": 3,
    "codebases": 12,
    "tasks": 45,
    "sessions": 156
  },
  "pool_size": 10,
  "pool_idle": 8
}
```

| Field | Type | Description |
|-------|------|-------------|
| `available` | boolean | Whether PostgreSQL is connected |
| `message` | string | Connection status message |
| `stats.workers` | integer | Total registered workers |
| `stats.codebases` | integer | Total registered codebases |
| `stats.tasks` | integer | Total tasks in database |
| `stats.sessions` | integer | Total sessions synced |
| `pool_size` | integer | Connection pool size |
| `pool_idle` | integer | Idle connections available |

---

### List All Sessions (Database)

Get all sessions across all codebases from PostgreSQL.

```http
GET /v1/opencode/database/sessions
GET /v1/opencode/database/sessions?limit=50&offset=0
```

**Query Parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 100 | Maximum sessions to return |
| `offset` | integer | 0 | Pagination offset |

**Response**

```json
{
  "sessions": [
    {
      "id": "sess_xyz789",
      "codebase_id": "cb_abc123",
      "codebase_name": "my-project",
      "codebase_path": "/home/user/my-project",
      "title": "Implementing OAuth2 authentication",
      "created_at": "2025-12-10T15:00:00Z",
      "updated_at": "2025-12-10T16:30:00Z",
      "summary": {
        "total_messages": 24,
        "model": "claude-sonnet-4-20250514"
      }
    }
  ],
  "total": 156,
  "limit": 100,
  "offset": 0,
  "source": "postgresql"
}
```

---

### List All Codebases (Database)

Get all registered codebases from PostgreSQL.

```http
GET /v1/opencode/database/codebases
```

**Response**

```json
{
  "codebases": [
    {
      "id": "cb_abc123",
      "name": "my-project",
      "path": "/home/user/my-project",
      "description": "Main application",
      "worker_id": "worker-1",
      "status": "idle",
      "created_at": "2025-12-10T10:00:00Z",
      "updated_at": "2025-12-10T15:30:00Z"
    }
  ],
  "total": 12,
  "source": "postgresql"
}
```

---

### List All Workers (Database)

Get all registered workers from PostgreSQL.

```http
GET /v1/opencode/database/workers
```

**Response**

```json
{
  "workers": [
    {
      "worker_id": "abc123",
      "name": "dev-vm-worker",
      "hostname": "dev-vm.internal",
      "capabilities": ["opencode", "build", "deploy", "test"],
      "status": "active",
      "registered_at": "2025-12-10T09:00:00Z",
      "last_seen": "2025-12-10T15:30:00Z"
    }
  ],
  "total": 3,
  "source": "postgresql"
}
```

---

## Workers

The Worker API enables [Agent Workers](../features/agent-worker.md) to connect, register codebases, and execute tasks.

### Register Worker

Register a worker with the server.

```http
POST /v1/opencode/workers/register
Content-Type: application/json
```

**Request Body**

```json
{
  "worker_id": "abc123",
  "name": "dev-vm-worker",
  "capabilities": ["opencode", "build", "deploy", "test"],
  "hostname": "dev-vm.internal"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `worker_id` | string | ✅ | Unique worker identifier |
| `name` | string | ✅ | Human-readable worker name |
| `capabilities` | array | ❌ | List of worker capabilities |
| `hostname` | string | ❌ | Machine hostname |

**Response**

```json
{
  "success": true,
  "worker_id": "abc123",
  "message": "Worker registered"
}
```

---

### Unregister Worker

Unregister a worker from the server.

```http
POST /v1/opencode/workers/{worker_id}/unregister
```

**Response**

```json
{
  "success": true,
  "message": "Worker unregistered"
}
```

---

### Stream Task Output

Stream real-time output from a task execution.

```http
POST /v1/opencode/tasks/{task_id}/output
Content-Type: application/json
```

**Request Body**

```json
{
  "worker_id": "abc123",
  "output": "Analyzing codebase structure...",
  "timestamp": "2025-12-10T15:30:05Z"
}
```

**Response**

```json
{
  "success": true
}
```

---

### Update Task Status

Update the status of a task (used by workers).

```http
PUT /v1/opencode/tasks/{task_id}/status
Content-Type: application/json
```

**Request Body**

```json
{
  "status": "completed",
  "worker_id": "abc123",
  "result": "Added 15 unit tests to the authentication module"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `status` | string | ✅ | New status: `running`, `completed`, `failed` |
| `worker_id` | string | ✅ | Worker identifier |
| `result` | string | ❌ | Task result (for completed) |
| `error` | string | ❌ | Error message (for failed) |

**Response**

```json
{
  "success": true,
  "task_id": "task_abc123",
  "status": "completed"
}
```

---

### Sync Sessions

Sync OpenCode sessions from a worker to the server.

```http
POST /v1/opencode/codebases/{codebase_id}/sessions/sync
Content-Type: application/json
```

**Request Body**

```json
{
  "worker_id": "abc123",
  "sessions": [
    {
      "id": "sess_xyz789",
      "title": "Implementing OAuth2 flow",
      "project_id": "2e35f00d",
      "created_at": "2025-12-10T15:00:00Z",
      "updated_at": "2025-12-10T16:30:00Z",
      "summary": {
        "total_messages": 24,
        "model": "claude-sonnet-4-20250514"
      }
    }
  ]
}
```

**Response**

```json
{
  "success": true,
  "synced": 5,
  "message": "Synced 5 sessions"
}
```

---

## Error Responses

All endpoints return errors in a consistent format:

```json
{
  "detail": "Codebase not found"
}
```

| Status Code | Description |
|-------------|-------------|
| `400` | Bad request - invalid parameters |
| `404` | Resource not found |
| `409` | Conflict - e.g., agent already running |
| `503` | OpenCode bridge not available |

---

## Examples

### Complete Workflow

```bash
# 1. Check status
curl https://codetether.run/v1/opencode/status

# 2. Register a codebase
curl -X POST https://codetether.run/v1/opencode/codebases \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-app",
    "path": "/home/user/my-app",
    "description": "My application"
  }'

# 3. List available models
curl https://codetether.run/v1/opencode/models

# 4. Trigger an agent
curl -X POST https://codetether.run/v1/opencode/codebases/cb_abc123/trigger \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Refactor the database module to use async/await",
    "agent": "build",
    "model": "anthropic/claude-sonnet-4-20250514"
  }'

# 5. Watch events (in another terminal)
curl -N https://codetether.run/v1/opencode/codebases/cb_abc123/events

# 6. Send follow-up message
curl -X POST https://codetether.run/v1/opencode/codebases/cb_abc123/message \
  -H "Content-Type: application/json" \
  -d '{"message": "Also add type hints"}'

# 7. Stop the agent
curl -X POST https://codetether.run/v1/opencode/codebases/cb_abc123/stop
```
