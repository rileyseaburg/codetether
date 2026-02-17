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

## CodeTether API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /v1/agent/status | Check CodeTether status (includes runtime info) |
| GET | /v1/agent/codebases | List registered codebases |
| POST | /v1/agent/codebases | Register a codebase |
| GET | /v1/agent/models | List available AI models |
| GET | /v1/agent/tasks | List all tasks |
| POST | /v1/agent/codebases/{id}/tasks | Create a task for a codebase |
| GET | /v1/agent/tasks/{id} | Get task details |
| PUT | /v1/agent/tasks/{id}/status | Update task status |
| POST | /v1/agent/tasks/{id}/output | Stream task output |
| POST | /v1/agent/tasks/{id}/cancel | Cancel a task |

## Worker API

Endpoints used by Agent Workers.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /v1/agent/workers/register | Register a worker |
| POST | /v1/agent/workers/{id}/unregister | Unregister a worker |
| POST | /v1/agent/codebases/{id}/sessions/sync | Sync sessions from worker |

## CodeTether Runtime API

Direct access to local CodeTether sessions without codebase registration.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /v1/agent/runtime/status | Check if CodeTether is available locally |
| GET | /v1/agent/runtime/projects | List all local projects |
| GET | /v1/agent/runtime/sessions | List all sessions (paginated) |
| GET | /v1/agent/runtime/sessions/{id} | Get session details |
| GET | /v1/agent/runtime/sessions/{id}/messages | Get session messages |
| GET | /v1/agent/runtime/sessions/{id}/parts | Get message content parts |

## Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /health | Health check |

See also: [CodeTether API](agent.md) | [Agent Worker](../features/agent-worker.md)
