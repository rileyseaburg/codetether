---
title: Zapier Integration
description: Connect CodeTether to 6,000+ apps with native Zapier integration
---

# Zapier Integration

CodeTether's native Zapier integration lets you connect AI agent workflows to 6,000+ apps without writing code. Automate task creation, monitor completions, manage agents, schedule recurring work, and integrate with your existing tools.

!!! success "No-Code Automation"
    Create powerful AI agent workflows by connecting CodeTether to Slack, Email, Google Sheets, Notion, and thousands more—all through Zapier's visual interface.

## Overview

The Zapier integration (v1.2.0) provides **18 components**:

- **OAuth2 Authentication**: Secure connection with Keycloak SSO
- **3 Triggers**: React to task creation, completion, and failure
- **9 Actions**: Create tasks, send messages (sync & async), target specific agents, start Ralph runs, create cron jobs, generate PRDs, and cancel tasks/runs
- **7 Searches**: Find tasks, agents, codebases, Ralph runs, AI models, and billing usage

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
| `status` | string | Current status (pending/working/completed/failed) |
| `priority` | number | Task priority |
| `codebase_id` | string | Associated codebase |
| `agent_type` | string | Agent type (build/plan/general/explore) |
| `created_at` | datetime | Creation timestamp |

**Use Cases:**

- Notify team in Slack when tasks are created
- Log all tasks to Google Sheets
- Create Jira tickets for tracking

### Task Completed

Fires when a task finishes successfully.

**Output Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `task_id` | string | Task identifier |
| `title` | string | Task title |
| `result` | string | Task output/result |
| `model` | string | AI model used |
| `completed_at` | datetime | Completion timestamp |

**Use Cases:**

- Send completion notification via email
- Update project management tools
- Trigger follow-up workflows
- Chain multiple AI tasks together

### Task Failed

Fires when a task fails.

**Output Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `task_id` | string | Task identifier |
| `title` | string | Task title |
| `error` | string | Error message |
| `model` | string | AI model used |
| `updated_at` | datetime | Failure timestamp |

**Use Cases:**

- Alert on-call engineer via PagerDuty
- Create incident in tracking system
- Retry with different parameters or model

---

## Actions

### Create Task

Create a new AI agent task in the queue.

**Input Fields:**

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `title` | Yes | string | Task title |
| `description` | No | text | Detailed task description |
| `codebase_id` | No | string | Target codebase (defaults to global) |
| `agent_type` | No | string | Agent type: build, plan, general, explore |
| `model` | No | string | AI model to use |
| `priority` | No | number | Priority (higher = more urgent) |

**Example Zap:**

```
Trigger: New email with subject containing "AI Task"
Action: Create Task
  - title: {{email_subject}}
  - description: {{email_body}}
  - agent_type: build
```

### Send Message

Send a synchronous message to an AI agent and receive a response.

**Input Fields:**

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `message` | Yes | text | Message content |
| `conversation_id` | No | string | Continue an existing conversation |

**Example Zap:**

```
Trigger: New Slack message in #ai-tasks
Action: Send Message
  - message: {{message_text}}
  - conversation_id: {{thread_ts}}
```

### Send Async Message

Send a message asynchronously — creates a task that workers pick up. Returns immediately with a task_id for tracking. Best for long-running operations.

**Input Fields:**

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `message` | Yes | text | Message/prompt for the agent |
| `conversation_id` | No | string | Continue existing thread |
| `codebase_id` | No | string | Target codebase |
| `priority` | No | number | Task priority |
| `notify_email` | No | string | Email to notify on completion |
| `model` | No | string | AI model (friendly name) |
| `model_ref` | No | string | Model ID in provider:model format |

**Example Zap:**

```
Trigger: New Typeform submission
Action: Send Async Message
  - message: "Analyze this feedback: {{response}}"
  - notify_email: {{user_email}}
```

### Send to Specific Agent

Send a message to a specific named agent. The task queues until that agent is available.

**Input Fields:**

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `agent_name` | Yes | string | Target agent name (from Find Agent search) |
| `message` | Yes | text | Message for the agent |
| `conversation_id` | No | string | Continue existing thread |
| `codebase_id` | No | string | Target codebase |
| `priority` | No | number | Task priority |
| `deadline_seconds` | No | number | Fail if not claimed within N seconds |
| `notify_email` | No | string | Email notification on completion |
| `model` | No | string | AI model preference |

**Example Zap:**

```
Trigger: New GitHub PR
Action: Send to Specific Agent
  - agent_name: codetether-reviewer
  - message: "Review PR #{{pr_number}}: {{pr_title}}"
  - deadline_seconds: 600
```

### Start Ralph Run

Start an autonomous Ralph development run from a PRD. Ralph implements user stories iteratively, runs tests, and commits changes.

**Input Fields:**

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `prd_json` | No | text | Full PRD as JSON (overrides story fields) |
| `project_name` | No | string | Project name |
| `branch_name` | No | string | Git branch for changes |
| `project_description` | No | text | What Ralph should build |
| `story_N_id/title/description/criteria` | No | string | Up to 10 user stories |
| `codebase_id` | No | string | Target codebase |
| `model` | No | string | AI model to use |
| `max_iterations` | No | number | Max retries per story (default: 10) |
| `run_mode` | No | string | sequential or parallel |

### Cancel Task

Cancel a running or pending task.

**Input Fields:**

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `task_id` | Yes | string | Task to cancel |

### Cancel Ralph Run

Cancel a running Ralph autonomous development run. The run stops after the current iteration completes.

**Input Fields:**

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `run_id` | Yes | string | Ralph run ID to cancel |

### Create Cron Job

Create a scheduled cron job that automatically triggers tasks on a recurring schedule.

**Input Fields:**

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `name` | Yes | string | Cron job name |
| `cron_expression` | Yes | string | Standard cron expression (e.g., `0 9 * * 1-5`) |
| `task_template` | Yes | text | Task message/prompt to run on schedule |
| `description` | No | text | What this cron job does |
| `timezone` | No | string | Timezone (default: UTC) |
| `enabled` | No | boolean | Start enabled (default: true) |

**Example Zap:**

```
Trigger: Button press in Slack
Action: Create Cron Job
  - name: "Daily Code Review"
  - cron_expression: "0 9 * * 1-5"
  - task_template: "Review all PRs merged in the last 24 hours"
  - timezone: "America/New_York"
```

### Generate PRD via Chat

Chat with AI to generate a Product Requirements Document with structured user stories. Use `conversation_id` to refine iteratively.

**Input Fields:**

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `message` | Yes | text | Describe your project or answer AI questions |
| `conversation_id` | No | string | Continue existing PRD chat |
| `codebase_id` | No | string | Target codebase for the PRD |

**Output Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `conversation_id` | string | Session ID for follow-up messages |
| `response` | string | AI response with PRD details |
| `has_prd` | boolean | Whether a complete PRD was generated |
| `prd_json` | string | Generated PRD as JSON (feed into Start Ralph Run) |

**Example Zap:**

```
Trigger: New Notion page in "Product Ideas"
Action: Generate PRD via Chat
  - message: "Create a PRD for: {{page_title}} - {{page_content}}"
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

### Find Ralph Run

Find a Ralph run by ID to check status and progress.

**Input Fields:**

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `run_id` | Yes | string | Ralph run ID |

**Output** includes status, progress (passed/total), story results, and timing.

### Find Ralph Runs

List Ralph runs with optional status filter.

**Input Fields:**

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `status` | No | string | pending, running, completed, failed, cancelled |
| `limit` | No | number | Max results (default: 20) |

### Find Agent

Discover registered worker agents in the network.

**Input Fields:**

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `name` | No | string | Filter by agent name (partial match) |

**Output Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Agent name |
| `description` | string | What the agent does |
| `url` | string | Agent endpoint URL |
| `streaming` | boolean | Supports streaming |
| `models_supported` | string | Comma-separated model list |
| `last_seen` | datetime | Last heartbeat |

### Find Codebase

Find registered codebases for targeting tasks and Ralph runs.

**Input Fields:**

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `name` | No | string | Filter by name (partial match) |

**Output** includes codebase ID, name, path, worker, and status.

### Find AI Models

Discover available AI models from registered workers.

**Input Fields:**

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `provider` | No | string | anthropic, openai, google, openrouter, minimax, xai |
| `search` | No | string | Filter by model name |

**Output Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `model_ref` | string | Model ID (e.g., `anthropic:claude-sonnet-4`) |
| `name` | string | Friendly model name |
| `provider` | string | Provider name |
| `workers_available` | number | How many workers support this model |

### Get Token Usage

Get aggregated token usage and billing summary.

**Input Fields:**

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `month` | No | string | Month as YYYY-MM (default: current) |

**Output Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `total_tokens` | number | Total tokens used |
| `input_tokens` | number | Input tokens |
| `output_tokens` | number | Output tokens |
| `total_cost` | number | Total cost in USD |
| `total_requests` | number | Number of requests |
| `budget_remaining` | number | Remaining budget |
| `spending_limit` | number | Current spending limit |

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
Then: Send to Specific Agent (codetether-builder)
Then: Comment on issue with task link
```

### Daily Summary

```
When: Every day at 9am
Search: Find tasks completed yesterday
Then: Send digest to Slack #team-updates
```

### Notion → PRD → Ralph

```
When: New Notion page in "Product Ideas"
Then: Generate PRD via Chat
Then: Start Ralph Run with generated PRD
Then: Notify in Slack with run link
```

### Budget Alert

```
When: Every Monday at 8am
Search: Get Token Usage
Filter: total_cost > 40
Then: Send Slack alert to #billing
```

### Auto-Retry Failed Tasks

```
Trigger: Task Failed
Action: Create Task (same title/description)
Filter: Only if retry_count < 3
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
| `agents:read` | Discover agents |
| `billing:read` | View usage and billing |
| `cronjobs:write` | Create and manage cron jobs |

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

1. **Check required fields**: Ensure title is provided
2. **Verify codebase exists**: Use "Find Codebase" search to get valid IDs
3. **Review Zapier logs**: Check the task history for errors

### Trigger Not Firing

1. **Verify connection**: Test the connection in Zapier
2. **Check filters**: Review any filter conditions
3. **Polling delay**: Zapier polls every 1-15 minutes depending on your plan

### Agent Not Found

1. **Use Find Agent search**: Verify the agent name matches exactly
2. **Check agent status**: Agent must have sent a heartbeat within 120 seconds
3. **Set a deadline**: Use `deadline_seconds` to fail fast on unavailable agents

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
