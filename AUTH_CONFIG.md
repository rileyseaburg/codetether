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
