# Zapier Integration Quick Start

This guide walks through connecting CodeTether to Zapier for workflow automation.

## Overview

CodeTether provides a simple REST API that Zapier can call to create and monitor AI-powered tasks. The integration uses webhooks for real-time updates when tasks complete.

## Prerequisites

- A CodeTether instance (self-hosted or managed)
- API key from CodeTether
- Zapier account

## Authentication

CodeTether supports two authentication methods for Zapier:

1. **API Key** (Recommended for quick setup)
2. **OAuth 2.0** (For production integrations)

### API Key Authentication

Your API key starts with `ct_` and can be found in your CodeTether dashboard under Settings > API Keys.

**Example Header:**
```
Authorization: Bearer ct_abc123...
```

### OAuth 2.0 Authentication

For production use, Zapier supports OAuth 2.0 with the CodeTether authorization server:

- **Authorization Endpoint:** `https://api.codetether.io/oauth/authorize`
- **Token Endpoint:** `https://api.codetether.io/oauth/token`
- **Scopes:** `tasks:read`, `tasks:write`, `automation:read`, `automation:write`

## Quick Start: Create a Zap

### Step 1: Create a Task with Webhook

Use Zapier's "Webhooks by Zapier" or make a direct HTTP POST to CodeTether:

**POST** `/v1/automation/tasks`

**Headers:**
```
Authorization: Bearer ct_your_api_key_here
Content-Type: application/json
```

**Body:**
```json
{
  "title": "Analyze customer feedback",
  "description": "Analyze the following customer feedback and summarize key points: {{feedback_text}}",
  "agent_type": "general",
  "model": "claude-sonnet",
  "webhook_url": "https://hooks.zapier.com/hooks/catch/123/abc/",
  "priority": 0
}
```

**Response:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "run_id": "660e8400-e29b-41d4-a716-446655440001",
  "status": "queued",
  "title": "Analyze customer feedback",
  "description": "Analyze the following customer feedback...",
  "created_at": "2025-01-19T10:30:00Z",
  "model": "claude-sonnet"
}
```

### Step 2: Set Up a Webhook Catcher in Zapier

1. Create a new Zap
2. Select **Webhooks by Zapier** as the trigger
3. Choose **Catch Hook**
4. Copy the webhook URL provided by Zapier
5. Use this URL as the `webhook_url` when creating tasks

### Step 3: Process the Webhook Response

When your task completes, CodeTether will send a POST request to your webhook:

**Webhook Payload:**
```json
{
  "event": "task_completed",
  "run_id": "660e8400-e29b-41d4-a716-446655440001",
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "result": "The feedback mentions three key areas: pricing concerns, feature requests for reporting, and positive sentiment about customer support.",
  "result": null,
  "timestamp": "2025-01-19T10:35:00Z"
}
```

## Available Webhook Events

CodeTether sends webhook notifications for these events:

- **task_started**: Task execution has begun
- **task_progress**: Task is making progress (optional)
- **task_completed**: Task finished successfully
- **task_failed**: Task encountered an error
- **task_needs_input**: Task requires additional information

## Rate Limiting

CodeTether enforces rate limits:
- **Default:** 60 requests per minute
- **Headers:** Each response includes rate limit info:
  - `X-RateLimit-Limit`: Your current limit
  - `X-RateLimit-Remaining`: Requests remaining
  - `X-RateLimit-Reset`: Unix timestamp when limit resets

## Idempotency

To prevent duplicate tasks on retries, include an `Idempotency-Key` header:

```
Idempotency-Key: uuid-v4
```

Subsequent requests with the same key will return the original task ID.

## Webhook Signature Verification (Optional)

For added security, configure a webhook signing secret in CodeTether:

1. Set `CODETETHER_WEBHOOK_SECRET` environment variable
2. CodeTether will include `X-CodeTether-Signature` header on webhooks
3. Verify signatures in Zapier using HMAC-SHA256:

**Zapier Code by Zapier:**
```javascript
const crypto = require('crypto');
const payload = JSON.stringify(bundle.rawRequest.json);
const signature = bundle.rawRequest.headers['x-codetether-signature'];
const secret = 'your_webhook_secret';

const expected = 'sha256=' + crypto
  .createHmac('sha256', secret)
  .update(payload)
  .digest('hex');

if (signature !== expected) {
  throw new Error('Invalid webhook signature');
}
```

## Example Zaps

### Zap 1: Email Analysis
1. **Trigger:** New email in Gmail
2. **Action:** CodeTether - Create Task (Analyze sentiment, extract topics)
3. **Trigger:** Webhook catch (CodeTether callback)
4. **Action:** Add to Google Sheet with analysis results

### Zap 2: Customer Support Triage
1. **Trigger:** New form submission (Typeform/JotForm)
2. **Action:** CodeTether - Create Task (Categorize issue, suggest response)
3. **Trigger:** Webhook catch
4. **Action:** Create Slack message in appropriate channel

### Zap 3: Document Summarization
1. **Trigger:** New file in Google Drive
2. **Action:** Extract file contents
3. **Action:** CodeTether - Create Task (Summarize document)
4. **Trigger:** Webhook catch
5. **Action:** Update Notion database with summary

## API Reference

### Create Task
```
POST /v1/automation/tasks
```

### Get Task Status
```
GET /v1/automation/tasks/{task_id}
```

### List Tasks
```
GET /v1/automation/tasks?status=completed&limit=50
```

## Troubleshooting

### Task Not Starting
- Check API key is valid
- Verify webhook URL format
- Check rate limit headers in response

### Webhook Not Received
- Verify webhook URL is publicly accessible
- Check Zapier webhook history
- Ensure task completed (check status via GET /tasks/{id})

### Signatures Failing
- Verify `CODETETHER_WEBHOOK_SECRET` is set
- Ensure you're using the raw JSON payload, not parsed
- Check character encoding (must be UTF-8)

## Support

- **Documentation:** https://docs.codetether.io
- **API Status:** https://status.codetether.io
- **Issues:** https://github.com/codetether/codetether/issues
