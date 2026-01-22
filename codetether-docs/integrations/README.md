# CodeTether Integration Documentation

Welcome to CodeTether's integration guides! This directory contains documentation for connecting CodeTether with popular automation platforms.

## Why Integrate?

CodeTether provides a powerful AI automation platform that can be integrated with:
- **Zapier** - Create automated workflows
- **n8n** - Build complex automation pipelines
- **Make (Integromat)** - Connect apps and services
- And more!

## Quick Start

Choose your platform:

- [Zapier Integration Guide](./zapier-quickstart.md)
- [n8n Integration Guide](./n8n-quickstart.md)
- [Make Integration Guide](./make-quickstart.md)

## Key Concepts

### Authentication

CodeTether supports multiple authentication methods:
- **API Key** - Simple Bearer token authentication (easiest)
- **OAuth 2.0** - For production integrations and public apps

### Webhook vs Polling

- **Webhooks** - Recommended for real-time updates
- **Polling** - Alternative when webhooks aren't available
- See [Async Polling Pattern](./async-polling-pattern.md) for details

### Rate Limiting

- Default: 60 requests per minute
- Headers included: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`

## API Reference

### Base URL
```
https://api.codetether.io/v1/automation
```

### Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/tasks` | POST | Create a new task |
| `/tasks/{id}` | GET | Get task status |
| `/tasks` | GET | List tasks with filters |

## Supported Platforms

### Zapier
- Quick Start: [Guide](./zapier-quickstart.md)
- App Manifest: [Manifest](./zapier-app-manifest.md)
- Webhooks support: ✅
- Polling support: ❌ (Webhooks only)

### n8n
- Quick Start: [Guide](./n8n-quickstart.md)
- Webhooks support: ✅
- Polling support: ✅

### Make
- Quick Start: [Guide](./make-quickstart.md)
- Webhooks support: ✅
- Polling support: ✅

## Examples

### Simple Task Creation

```bash
curl -X POST https://api.codetether.io/v1/automation/tasks \
  -H "Authorization: Bearer ct_your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Analyze feedback",
    "description": "Summarize this customer feedback...",
    "agent_type": "general",
    "model": "claude-sonnet"
  }'
```

### Task Webhook Payload

```json
{
  "event": "task_completed",
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "result": "Summary of the analysis...",
  "timestamp": "2025-01-19T10:35:00Z"
}
```

## Webhook Signature Verification

For added security, configure a webhook signing secret:

```bash
export CODETETHER_WEBHOOK_SECRET=your_secret_here
```

Then verify signatures using HMAC-SHA256.

## Idempotency

Prevent duplicate tasks with the `Idempotency-Key` header:

```bash
curl -X POST https://api.codetether.io/v1/automation/tasks \
  -H "Authorization: Bearer ct_your_api_key" \
  -H "Idempotency-Key: <uuid>" \
  ...
```

## Getting Help

- **Documentation:** https://docs.codetether.io
- **GitHub Issues:** https://github.com/codetether/codetether/issues
- **Community:** Coming soon!

## Contributing

Found an issue or want to improve the docs?
1. Fork the repository
2. Edit the documentation
3. Submit a pull request

## Gap Analysis

For details on current capabilities and planned features, see the [Gap Analysis](./gap-analysis.md).
