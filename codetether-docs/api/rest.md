---
title: REST Endpoints
description: REST API reference
---

# REST Endpoints

CodeTether exposes REST APIs for management and monitoring.

## Monitor API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /v1/monitor/agents | List agents |
| GET | /v1/monitor/messages | Get messages |
| GET | /v1/monitor/stats | Get statistics |
| GET | /v1/monitor/workers | List connected workers |

## OpenCode API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /v1/opencode/status | Check OpenCode status (includes runtime info) |
| GET | /v1/opencode/codebases | List registered codebases |
| POST | /v1/opencode/codebases | Register a codebase |
| GET | /v1/opencode/models | List available AI models |
| GET | /v1/opencode/tasks | List all tasks |
| POST | /v1/opencode/codebases/{id}/tasks | Create a task for a codebase |
| GET | /v1/opencode/tasks/{id} | Get task details |
| PUT | /v1/opencode/tasks/{id}/status | Update task status |
| POST | /v1/opencode/tasks/{id}/output | Stream task output |
| POST | /v1/opencode/tasks/{id}/cancel | Cancel a task |

## Worker API

Endpoints used by Agent Workers.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /v1/opencode/workers/register | Register a worker |
| POST | /v1/opencode/workers/{id}/unregister | Unregister a worker |
| POST | /v1/opencode/codebases/{id}/sessions/sync | Sync sessions from worker |

## OpenCode Runtime API

Direct access to local OpenCode sessions without codebase registration.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /v1/opencode/runtime/status | Check if OpenCode is available locally |
| GET | /v1/opencode/runtime/projects | List all local projects |
| GET | /v1/opencode/runtime/sessions | List all sessions (paginated) |
| GET | /v1/opencode/runtime/sessions/{id} | Get session details |
| GET | /v1/opencode/runtime/sessions/{id}/messages | Get session messages |
| GET | /v1/opencode/runtime/sessions/{id}/parts | Get message content parts |

## Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /health | Health check |

See also: [OpenCode API](opencode.md) | [Agent Worker](../features/agent-worker.md)
