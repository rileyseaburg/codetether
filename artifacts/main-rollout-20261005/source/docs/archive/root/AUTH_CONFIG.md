# Production Auth & Billing Configuration

## Overview

CodeTether uses three systems for auth and billing:
- **Keycloak** — Enterprise SSO (OAuth2/OIDC)
- **OPA** — Policy-based authorization (RBAC)
- **Stripe** — Subscription billing

## Keycloak

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `KEYCLOAK_URL` | No | Keycloak base URL (default: `https://auth.quantum-forge.io`) |
| `KEYCLOAK_REALM` | No | Realm name (default: `quantum-forge`) |
| `KEYCLOAK_CLIENT_ID` | No | OAuth client ID (default: `a2a-monitor`) |
| `KEYCLOAK_CLIENT_SECRET` | **Yes** | OAuth client secret — **must be set** |
| `KEYCLOAK_ADMIN_USERNAME` | No | Admin user for management API |
| `KEYCLOAK_ADMIN_PASSWORD` | No | Admin password for management API |

### Helm Deployment

```bash
helm upgrade a2a-server chart/a2a-server \
  --set keycloak.clientSecret=YOUR_CLIENT_SECRET
```

Or create a sealed secret and reference it in your values override.

## OPA Authorization

OPA runs in one of two modes:

### Sidecar Mode (production)
Enable the OPA sidecar container in the Helm chart:
```yaml
opa:
  enabled: true
```
This deploys OPA alongside the server and loads Rego policies from the `policies/` directory.

### Local Mode (default when sidecar disabled)
When `opa.enabled=false` in Helm, the chart automatically sets `OPA_LOCAL_MODE=true`.
Policies are evaluated in-process using `policies/data.json` — same RBAC rules, no sidecar needed.

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPA_ENABLED` | `true` | Master toggle for policy enforcement |
| `OPA_LOCAL_MODE` | `false` | Evaluate policies in-process (no sidecar) |
| `OPA_FAIL_OPEN` | `false` | Allow requests when OPA is unreachable |
| `OPA_URL` | `http://localhost:8181` | OPA sidecar URL |

## Stripe Billing

### Option 1: Environment Variables

```bash
export STRIPE_API_KEY=sk_live_...
export STRIPE_WEBHOOK_SECRET=whsec_...
```

### Option 2: HashiCorp Vault

Store at path `kv/codetether/stripe`:
```bash
vault kv put kv/codetether/stripe \
  api_key=sk_live_... \
  webhook_secret=whsec_...
```

### Option 3: Helm Values

```bash
helm upgrade a2a-server chart/a2a-server \
  --set stripe.apiKey=sk_live_... \
  --set stripe.webhookSecret=whsec_...
```

### Price IDs

| Plan | Price | Stripe Price ID |
|------|-------|-----------------|
| Free | $0/mo | — |
| Pro | $49/mo | `price_1SoawKE8yr4fu4JjkHQA2Y2c` |
| Enterprise | $199/mo | `price_1SoawKE8yr4fu4Jj7iDEjsk6` |

### Webhook Endpoint

Configure your Stripe webhook to send events to:
```
https://your-server/v1/billing/webhooks/stripe
```

Required events: `checkout.session.completed`, `customer.subscription.updated`,
`customer.subscription.deleted`, `invoice.payment_succeeded`, `invoice.payment_failed`

## CLI Authentication

The Rust CLI supports two auth methods:

### CodeTether Server Login
```bash
codetether auth login --server https://api.codetether.io
```
Prompts for email/password, stores JWT in `~/.config/codetether-agent/credentials.json`.

### GitHub Copilot Device Flow
```bash
codetether auth copilot --client-id YOUR_OAUTH_CLIENT_ID
```
Opens browser for GitHub device authorization, stores token in Vault.

### Worker Token
For headless workers, set the token directly:
```bash
export CODETETHER_TOKEN=your_jwt_token
```

## Redis Session Store

Keycloak sessions persist to Redis when available:
```bash
export A2A_REDIS_URL=redis://localhost:6379  # or REDIS_URL
```
Falls back to in-memory storage if Redis is unavailable.

## Event Stream Audit Logging

CodeTether supports structured JSONL event sourcing for compliance with SOC 2, FedRAMP, and ATO requirements. Every agent turn, tool call, and handoff is captured with timestamps, session IDs, byte-range offsets, and execution duration.

### Enable Event Streaming

```bash
export CODETETHER_EVENT_STREAM_PATH="/tmp/event-streams"
```

Events are written to `{CODETETHER_EVENT_STREAM_PATH}/{session_id}/{timestamp}-chat-events-{start_byte}-{end_byte}.jsonl`

### Event Schema

```json
{
  "recorded_at": "2026-02-13T04:16:56.465006066+00:00",
  "workspace": "/home/riley/A2A-Server-MCP",
  "session_id": "36d04218-2a47-4fbe-8579-02c21be775bc",
  "role": "tool",
  "agent_name": null,
  "message_type": "tool_result",
  "content": "✓ bash",
  "tool_name": "bash",
  "tool_success": true,
  "tool_duration_ms": 22515,
  "sequence": 12
}
```

### Byte-Range Offsets

The filename format `{start_byte}-{end_byte}` enables random-access replay without reading the entire session log. This is essential for:
- **Incident reviews** — Seek to exact timestamps
- **Compliance audits** — Prove specific actions occurred
- **Debugging** — Reconstruct session state at any point

### Integration with S3/R2 (Automatic Archival)

For permanent immutable storage, event streams are automatically uploaded to S3/R2 after each session completes. This requires no additional setup beyond configuring the environment variables.

#### How It Works

1. When a session completes (after `prompt()` or `prompt_with_events()` returns), the server automatically archives all event files to S3/R2
2. Files are uploaded to `{bucket}/{prefix}/{session_id}/{timestamp}-chat-events-{start}-{end}.jsonl`
3. Uploads happen asynchronously — they don't block the session response
4. If S3 upload fails, the error is logged but doesn't fail the session

#### Configuration

```bash
# Required: S3 bucket name
export CODETETHER_S3_BUCKET="codetether-audit-events"

# Optional: Path prefix for uploaded files
export CODETETHER_S3_PREFIX="events/"

# Optional: S3 endpoint (omit for AWS S3, set for R2/MinIO)
export CODETETHER_S3_ENDPOINT="https://account-id.r2.cloudflarestorage.com"

# Optional: S3 credentials (omit for IAM role / instance profile)
export CODETETHER_S3_ACCESS_KEY="your-access-key"
export CODETETHER_S3_SECRET_KEY="your-secret-key"

# Optional: S3 region (default: us-east-1)
export CODETETHER_S3_REGION="us-east-1"
```

Supported storage backends:
- **AWS S3** — Omit `CODETETHER_S3_ENDPOINT`
- **Cloudflare R2** — Set `CODETETHER_S3_ENDPOINT` to your R2 endpoint
- **MinIO** — Set `CODETETHER_S3_ENDPOINT` to your MinIO server

### Replay API

To replay a session from byte offsets, use the replay API endpoints:

**1. Get event file index (list all byte-range files for a session):**
```
GET /v1/audit/replay/index?session_id={session_id}
```

Response:
```json
[
  {
    "filename": "20260213T041710Z-chat-events-00000000000000101278-00000000000000101588.jsonl",
    "start_offset": 101278,
    "end_offset": 101588,
    "size_bytes": 310
  }
]
```

**2. Replay events by byte range:**
```
GET /v1/audit/replay?session_id={session_id}&start_offset={byte}&end_offset={byte}
```

Query Parameters:
| Parameter | Required | Description |
|-----------|----------|-------------|
| `session_id` | Yes | Session UUID |
| `start_offset` | No | Starting byte offset |
| `end_offset` | No | Ending byte offset |
| `limit` | No | Max events to return (default: 1000, max: 10000) |
| `tool_name` | No | Filter by tool name (e.g., `bash`, `edit`) |

Response:
```json
[
  {
    "recorded_at": "2026-02-13T04:16:56.465006066+00:00",
    "workspace": "/home/riley/A2A-Server-MCP",
    "session_id": "36d04218-2a47-4fbe-8579-02c21be775bc",
    "role": "tool",
    "message_type": "tool_result",
    "content": "✓ bash",
    "tool_name": "bash",
    "tool_success": true,
    "tool_duration_ms": 22515,
    "sequence": 12
  }
]
```

**Example: Get all bash tool executions for a session:**
```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8080/v1/audit/replay?session_id=abc123&tool_name=bash"
```

**Example: Seek to specific byte offset (incident review):**
```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8080/v1/audit/replay?session_id=abc123&start_offset=10000&end_offset=50000"
```
