# Make (Integromat) Integration Quick Start

Use HTTP modules and webhooks to connect CodeTether with Make.

## Quick Start

1. Create a **Custom webhook** module in Make
2. Add an **HTTP** module to POST to `/v1/automation/tasks`
3. Use webhook URL in `webhook_url` parameter
4. Process results in subsequent modules

## Example

```
Google Forms → HTTP (CodeTether) → Webhook → Google Sheets
```

## Authentication

Header: `Authorization: Bearer ct_your_api_key_here`

## Troubleshooting

- Check API key format (ct_*)
- Verify webhook is public
- Check scenario logs
