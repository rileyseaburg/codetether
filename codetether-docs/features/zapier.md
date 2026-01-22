---
title: Zapier Integration
description: Connect CodeTether to 5,000+ apps with native Zapier integration
---

# Zapier Integration

CodeTether's native Zapier integration lets you connect AI agent workflows to 5,000+ apps without writing code. Automate task creation, monitor completions, and integrate with your existing tools.

!!! success "No-Code Automation"
    Create powerful AI agent workflows by connecting CodeTether to Slack, Email, Google Sheets, Notion, and thousands more—all through Zapier's visual interface.

## Overview

The Zapier integration provides:

- **OAuth2 Authentication**: Secure connection with Keycloak SSO
- **Triggers**: React to events like task creation and completion
- **Actions**: Create tasks, send messages, cancel tasks
- **Searches**: Find tasks by ID or status

---

## Getting Started

### 1. Connect Your Account

1. In Zapier, search for "CodeTether"
2. Click "Connect"
3. Sign in with your CodeTether credentials (Keycloak)
4. Authorize Zapier to access your account

### 2. Create Your First Zap

**Example: Slack to AI Task**

1. **Trigger**: New message in Slack channel
2. **Action**: Create task in CodeTether
3. **Result**: AI agent processes the request

---

## Triggers

### New Task

Fires when a new task is created in CodeTether.

**Output Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `task_id` | string | Unique task identifier |
| `title` | string | Task title |
| `status` | string | Current status (pending/running/completed/failed) |
| `codebase_id` | string | Associated codebase |
| `created_at` | datetime | Creation timestamp |
| `agent_type` | string | Agent type (build/plan/general/explore) |

**Use Cases:**

- Notify team in Slack when tasks are created
- Log all tasks to Google Sheets
- Create Jira tickets for tracking

### Task Completed

Fires when a task completes successfully.

**Output Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `task_id` | string | Task identifier |
| `title` | string | Task title |
| `result` | string | Task output/result |
| `duration_seconds` | number | Execution time |
| `completed_at` | datetime | Completion timestamp |

**Use Cases:**

- Send completion notification via email
- Update project management tools
- Trigger follow-up workflows

### Task Failed

Fires when a task fails.

**Output Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `task_id` | string | Task identifier |
| `error` | string | Error message |
| `retry_count` | number | Number of retry attempts |
| `failed_at` | datetime | Failure timestamp |

**Use Cases:**

- Alert on-call engineer via PagerDuty
- Create incident in tracking system
- Retry with different parameters

---

## Actions

### Create Task

Create a new AI agent task.

**Input Fields:**

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `title` | Yes | string | Task title |
| `prompt` | Yes | string | Instructions for the AI agent |
| `codebase_id` | No | string | Target codebase (uses global if not specified) |
| `agent_type` | No | string | Agent type (default: build) |
| `model` | No | string | LLM model to use |
| `priority` | No | number | Task priority (higher = more urgent) |

**Example Zap:**

```
Trigger: New email with subject containing "AI Task"
Action: Create Task
  - title: {{email_subject}}
  - prompt: {{email_body}}
  - agent_type: build
```

### Send Message

Send a message to an existing conversation/session.

**Input Fields:**

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `message` | Yes | string | Message content |
| `conversation_id` | No | string | Existing conversation to continue |
| `codebase_id` | No | string | Target codebase |

**Example Zap:**

```
Trigger: New Slack message in #ai-tasks
Action: Send Message
  - message: {{message_text}}
  - conversation_id: {{thread_ts}}
```

### Cancel Task

Cancel a running or pending task.

**Input Fields:**

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `task_id` | Yes | string | Task to cancel |

**Example Zap:**

```
Trigger: Slack reaction added (🛑)
Action: Cancel Task
  - task_id: {{original_message_task_id}}
```

---

## Searches

### Find Task

Search for a task by ID or status.

**Input Fields:**

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `task_id` | No | string | Exact task ID |
| `status` | No | string | Filter by status |
| `codebase_id` | No | string | Filter by codebase |

**Output:**

Returns matching task(s) with full details.

**Example Zap:**

```
Trigger: Scheduled (every hour)
Search: Find Task
  - status: failed
Action: Send email with failed tasks
```

---

## Popular Automations

### Slack → AI Development

```
When: New message in #dev-requests
Then: Create CodeTether task
Then: Send Slack reply with task ID
```

### Email → Code Review

```
When: Email received with subject "Review:"
Then: Create task with agent_type: plan
Then: Send review results via email
```

### GitHub Issue → AI Fix

```
When: GitHub issue labeled "ai-fix"
Then: Create CodeTether task with issue description
Then: Comment on issue with task link
```

### Daily Summary

```
When: Every day at 9am
Search: Find tasks completed yesterday
Then: Send digest to Slack #team-updates
```

---

## Configuration

### OAuth2 Scopes

The Zapier app requests these scopes:

| Scope | Description |
|-------|-------------|
| `tasks:read` | List and view tasks |
| `tasks:write` | Create and cancel tasks |
| `messages:write` | Send messages |
| `codebases:read` | List codebases |

### Rate Limits

| Tier | Requests/minute | Concurrent tasks |
|------|-----------------|------------------|
| Free | 60 | 5 |
| Pro | 300 | 25 |
| Enterprise | Unlimited | Unlimited |

---

## Troubleshooting

### Authentication Failed

1. **Re-authorize**: Disconnect and reconnect in Zapier
2. **Check credentials**: Verify your CodeTether login works
3. **Token expired**: Zapier handles refresh automatically, but try reconnecting

### Task Not Created

1. **Check required fields**: Ensure title and prompt are provided
2. **Verify codebase exists**: Use valid codebase_id or omit for global
3. **Review Zapier logs**: Check the task history for errors

### Trigger Not Firing

1. **Verify connection**: Test the connection in Zapier
2. **Check filters**: Review any filter conditions
3. **Webhook delay**: Allow up to 5 minutes for events

---

## API Reference

For direct API access (beyond Zapier), see:

- [REST API](../api/rest.md)
- [JSON-RPC API](../api/jsonrpc.md)
- [Authentication](../auth/overview.md)

---

## Next Steps

- [Getting Started](../getting-started/quickstart.md) - Set up CodeTether
- [Agent Worker](agent-worker.md) - Deploy workers for task execution
- [Ralph](ralph.md) - Autonomous development with PRDs
