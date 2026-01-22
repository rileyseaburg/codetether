# n8n Integration Quick Start

This guide walks through connecting CodeTether to n8n for workflow automation.

## Overview

n8n can integrate with CodeTether using HTTP Request nodes. The integration supports creating tasks, polling for status, and receiving webhooks when tasks complete.

## Prerequisites

- n8n instance (self-hosted or cloud)
- CodeTether instance (self-hosted or managed)
- CodeTether API key

## Quick Start

### Option 1: Webhook-Based (Recommended)

Use webhooks for real-time updates when tasks complete.

#### Step 1: Create a Webhook Node in n8n

1. Add a new node: **Webhook** node
2. Set path (e.g., `/codetether-callback`)
3. Set method: **POST**
4. Click "Listen for Test Event"
5. Copy the webhook URL

The URL will look like: `https://your-n8n-instance.com/webhook/codetether-callback`

#### Step 2: Create a Task in CodeTether

Add an **HTTP Request** node before your webhook node:

**HTTP Request Node Configuration:**
- **Method:** POST
- **URL:** `https://api.codetether.io/v1/automation/tasks`
- **Authentication:** Generic Credential Type > Header Auth
- **Body:** JSON
  ```json
  {
    "title": "{{ $json.title }}",
    "description": "{{ $json.description }}",
    "agent_type": "general",
    "model": "claude-sonnet",
    "webhook_url": "https://your-n8n-instance.com/webhook/codetether-callback"
  }
  ```

#### Step 3: Process the Webhook Response

When CodeTether calls your webhook, you'll receive task completion data.

## Example Workflows

### Workflow 1: Email Analysis

```
Gmail Trigger → Extract Body → Create CodeTether Task → Webhook → Process Result → Slack
```

## Authentication

Use Header Authentication with your API key starting with `ct_`:

```
Authorization: Bearer ct_your_api_key_here
```

## Troubleshooting

- Check API key format
- Verify webhook URL is public
- Check n8n execution logs
