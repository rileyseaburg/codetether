---
title: OpenCode API
description: API reference for OpenCode integration - codebases, sessions, and AI coding agents
---

# OpenCode API

The OpenCode API provides integration with AI coding agents. It manages codebases, sessions, tasks, and real-time agent interactions.

!!! info "Base URL"
    All OpenCode endpoints are prefixed with `/v1/opencode`
    ```
    https://agentmesh.example.com/v1/opencode/...
    ```

## Status

### Check OpenCode Status

Check if the OpenCode bridge is available and initialized.

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
  "auto_start": true
}
```

| Field | Type | Description |
|-------|------|-------------|
| `available` | boolean | Whether OpenCode bridge is initialized |
| `message` | string | Human-readable status message |
| `opencode_binary` | string | Path to OpenCode executable |
| `registered_codebases` | integer | Number of registered codebases |
| `auto_start` | boolean | Whether agents auto-start on trigger |

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
curl https://agentmesh.run/v1/opencode/status

# 2. Register a codebase
curl -X POST https://agentmesh.run/v1/opencode/codebases \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-app",
    "path": "/home/user/my-app",
    "description": "My application"
  }'

# 3. List available models
curl https://agentmesh.run/v1/opencode/models

# 4. Trigger an agent
curl -X POST https://agentmesh.run/v1/opencode/codebases/cb_abc123/trigger \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Refactor the database module to use async/await",
    "agent": "build",
    "model": "anthropic/claude-sonnet-4-20250514"
  }'

# 5. Watch events (in another terminal)
curl -N https://agentmesh.run/v1/opencode/codebases/cb_abc123/events

# 6. Send follow-up message
curl -X POST https://agentmesh.run/v1/opencode/codebases/cb_abc123/message \
  -H "Content-Type: application/json" \
  -d '{"message": "Also add type hints"}'

# 7. Stop the agent
curl -X POST https://agentmesh.run/v1/opencode/codebases/cb_abc123/stop
```
