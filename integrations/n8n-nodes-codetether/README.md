# n8n Community Node: CodeTether

This is an [n8n](https://n8n.io/) community node that lets you use [CodeTether](https://codetether.io) AI task automation in your n8n workflows.

CodeTether runs long-running AI tasks (code generation, data analysis, document processing) and delivers results via webhook, email, or API polling.

[n8n](https://n8n.io/) is a [fair-code licensed](https://docs.n8n.io/reference/license/) workflow automation platform.

## Installation

Follow the [n8n community node installation guide](https://docs.n8n.io/integrations/community-nodes/installation/) to install this node.

```bash
# In your n8n instance
npm install n8n-nodes-codetether
```

Or install via the n8n UI: **Settings → Community Nodes → Install → `n8n-nodes-codetether`**

## Credentials

You need a CodeTether API key to use this node:

1. Log in to your CodeTether dashboard
2. Go to **Settings → API Keys**
3. Create a new key (starts with `ct_`)
4. In n8n, add a new **CodeTether API** credential and paste your key

For self-hosted CodeTether, update the **API Domain** field to your instance URL.

## Nodes

### CodeTether (Action)

| Operation | Description |
|-----------|-------------|
| **Create Task** | Submit a prompt for AI execution. Returns `task_id` immediately. |
| **Get Task** | Retrieve current status and result of a task. |
| **Get Many Tasks** | List tasks with optional status filter. |
| **Wait for Completion** | Poll a task — returns empty when still running (use with Loop node). |
| **Cancel Task** | Cancel a queued or running task. |

### CodeTether Trigger

Webhook-based trigger that starts workflows when CodeTether fires events:

| Event | Description |
|-------|-------------|
| Task Completed | Task finished successfully with results |
| Task Failed | Task encountered an error |
| Task Started | Worker began processing the task |
| Any Event | Fires on any task lifecycle event |

Supports optional **HMAC signature verification** for security.

## Usage

### Pattern 1: Fire and Forget (Webhook Callback)

```
Schedule Trigger → CodeTether (Create Task, webhook_url = n8n webhook URL) → done

CodeTether Trigger → process result → Slack / Email / Google Sheets
```

1. Use the **Create Task** operation with `webhook_url` set to your CodeTether Trigger webhook URL
2. The trigger fires when the task completes, continuing the workflow

### Pattern 2: Create and Poll

```
Trigger → CodeTether (Create Task) → Loop → Wait 10s → CodeTether (Wait for Completion) → IF status=completed → process result
```

1. **Create Task** returns a `task_id`
2. Use a **Loop** node with **CodeTether Wait for Completion** inside
3. Add a **Wait** node (10-30s) between iterations
4. When the task finishes, the poll node returns the full result

### Pattern 3: Batch Processing

```
Read Spreadsheet → Split In Batches → CodeTether (Create Task) → collect task_ids → poll all
```

## Resources

- [CodeTether Documentation](https://codetether.io/docs)
- [Automation API Reference](https://codetether.io/docs/api/automation)
- [n8n Community Nodes Documentation](https://docs.n8n.io/integrations/community-nodes/)

## License

[MIT](LICENSE)
