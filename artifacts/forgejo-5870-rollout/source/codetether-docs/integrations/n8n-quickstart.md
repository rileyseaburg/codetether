# n8n Integration Quick Start

Connect CodeTether AI task automation to your n8n workflows. Create tasks, poll for results, and receive webhook callbacks — all from n8n.

## Two Integration Methods

| Method | Best For | Setup Time |
|--------|----------|------------|
| **Community Node** (recommended) | Native n8n experience, credential management | 2 min |
| **HTTP Request Node** | No extra install, full control | 5 min |

---

## Method 1: Community Node (Recommended)

### Install

In your n8n instance:

**Settings → Community Nodes → Install → `n8n-nodes-codetether`**

Or via CLI:

```bash
npm install n8n-nodes-codetether
```

### Configure Credentials

1. Open any workflow → Add node → Search "CodeTether"
2. Click **Create New Credential**
3. Enter your API key (starts with `ct_`)
4. For self-hosted: update **API Domain** to your instance URL

### Create a Task

1. Add a **CodeTether** node
2. Operation: **Create Task**
3. Fill in Title and Description (your AI prompt)
4. Optionally set Model, Agent Type, Webhook URL

The node returns `task_id` and `status: queued`.

### Poll for Result

1. Add a **Loop** node after Create Task
2. Inside the loop: **Wait** (15s) → **CodeTether** (Wait for Completion)
3. Connect the "done" output to your next step

### Receive Webhook Callback

1. Add a **CodeTether Trigger** node to a separate workflow
2. Select event: **Task Completed**
3. Copy the trigger's webhook URL
4. Pass that URL as `webhook_url` in your Create Task node

---

## Method 2: HTTP Request Node

Works without installing any community node.

### Step 1: Set Up Authentication

Create a **Header Auth** credential:

- **Name:** `Authorization`
- **Value:** `Bearer ct_your_api_key_here`

### Step 2: Create a Task

Add an **HTTP Request** node:

| Field | Value |
|-------|-------|
| Method | POST |
| URL | `https://api.codetether.io/v1/automation/tasks` |
| Authentication | Header Auth |
| Body Type | JSON |

Body:
```json
{
  "title": "Analyze customer feedback",
  "description": "Read the attached CSV of customer reviews and produce a sentiment analysis report with key themes and recommended actions.",
  "agent_type": "general",
  "model": "claude-sonnet-4"
}
```

Response:
```json
{
  "task_id": "a1b2c3d4-...",
  "run_id": "e5f6g7h8-...",
  "status": "queued",
  "title": "Analyze customer feedback",
  "created_at": "2026-02-10T12:00:00Z"
}
```

### Step 3: Poll for Completion

Add a polling loop:

```
Create Task → Wait 15s → HTTP GET /v1/automation/tasks/{task_id} → IF status=completed → next step
                ↑                                                          ↓ (else)
                └──────────────────────────────────────────────────────────┘
```

**HTTP Request** node for polling:

| Field | Value |
|-------|-------|
| Method | GET |
| URL | `https://api.codetether.io/v1/automation/tasks/{{ $('Create Task').item.json.task_id }}` |
| Authentication | Header Auth |

### Step 4: Handle the Result

Response when complete:
```json
{
  "task_id": "a1b2c3d4-...",
  "status": "completed",
  "result_summary": "Analyzed 2,847 reviews. Overall sentiment: 72% positive...",
  "runtime_seconds": 145,
  "completed_at": "2026-02-10T12:02:25Z"
}
```

### Alternative: Webhook Callback

Instead of polling, pass a webhook URL when creating the task:

```json
{
  "title": "Analyze customer feedback",
  "description": "...",
  "webhook_url": "https://your-n8n.example.com/webhook/codetether-callback"
}
```

Then add a **Webhook** node in a separate workflow:
- Path: `codetether-callback`
- Method: POST

CodeTether will POST the result to your webhook when done.

---

## Ready-to-Import Workflow Templates

Import these directly into n8n via **Workflows → Import from File**:

| Template | Description |
|----------|-------------|
| [`create-and-poll.json`](../../../integrations/n8n-nodes-codetether/workflows/create-and-poll.json) | Scheduled task creation with polling loop |
| [`webhook-callback.json`](../../../integrations/n8n-nodes-codetether/workflows/webhook-callback.json) | Webhook-based callback handler |
| [`gmail-analysis-to-slack.json`](../../../integrations/n8n-nodes-codetether/workflows/gmail-analysis-to-slack.json) | Gmail → AI analysis → Slack notification |

---

## API Reference

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/automation/tasks` | Create a new task |
| GET | `/v1/automation/tasks/{id}` | Get task status |
| GET | `/v1/automation/tasks` | List tasks (with `?status=` filter) |
| DELETE | `/v1/automation/tasks/{id}` | Cancel a task |
| GET | `/v1/automation/me` | Test auth / get user info |

### Task Statuses

| Status | Description |
|--------|-------------|
| `queued` | Waiting for a worker |
| `running` | AI agent is processing |
| `needs_input` | Agent needs clarification |
| `completed` | Finished with result |
| `failed` | Task failed |
| `cancelled` | Cancelled by user |

### Models

`claude-sonnet-4`, `claude-opus`, `claude-haiku`, `gpt-4o`, `gpt-4.1`, `gemini-2.5-pro`, `gemini-2.5-flash`, `grok-3`, `minimax-m2.1`, `o3`, `o3-mini`

### Rate Limits

60 requests/minute per API key. Response headers:

```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 55
X-RateLimit-Reset: 1707577200
```

### Idempotency

Include `Idempotency-Key` header to prevent duplicate tasks on retry:

```
POST /v1/automation/tasks
Idempotency-Key: my-unique-key-123
```

---

## Webhook Payload

When using `webhook_url`, CodeTether sends:

```json
{
  "event": "task_completed",
  "run_id": "e5f6g7h8-...",
  "task_id": "a1b2c3d4-...",
  "status": "completed",
  "result": "Full result text...",
  "error": null,
  "timestamp": "2026-02-10T12:02:25Z"
}
```

### Signature Verification

If configured, webhooks include HMAC-SHA256 signatures:

```
X-CodeTether-Signature: sha256=abc123...
X-CodeTether-Timestamp: 1707577200
```

Verify in n8n with a **Code** node:

```javascript
const crypto = require('crypto');
const secret = 'your-webhook-secret';
const payload = JSON.stringify($json.body);
const expected = 'sha256=' + crypto.createHmac('sha256', secret).update(payload).digest('hex');
const actual = $json.headers['x-codetether-signature'];

if (actual !== expected) {
  throw new Error('Invalid webhook signature');
}

return $json;
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| 401 Unauthorized | Check API key starts with `ct_` and is valid |
| 429 Too Many Requests | You're over 60 req/min. Check `Retry-After` header |
| Task stuck in `queued` | Verify workers are running (`GET /v1/automation/tasks/{id}`) |
| Webhook not received | Ensure URL is publicly accessible; check n8n execution logs |
| Duplicate tasks on retry | Add `Idempotency-Key` header to your create request |
