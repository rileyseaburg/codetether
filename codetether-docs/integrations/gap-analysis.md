---
title: Integration Gap Analysis
description: Gaps between CodeTether's current integration capabilities and Zapier's "Powered by Zapier" standards
---

# Integration Gap Analysis

This document identifies gaps between CodeTether's current automation platform integration capabilities and the standards set by Zapier's "Powered by Zapier" platform (their embedded automation infrastructure).

**Reference Documentation Analyzed:**
- [Zapier Workflow API](https://docs.zapier.com/powered-by-zapier/zap-creation/getting-started)
- [Zapier Action Runs](https://docs.zapier.com/powered-by-zapier/running-actions/getting-started)
- [Zapier OAuth 2.0 Authentication](https://docs.zapier.com/powered-by-zapier/authentication/methods/user-access-token)
- [Zapier Rate Limiting](https://docs.zapier.com/powered-by-zapier/api-reference/rate-limiting)
- [Zapier Quick Account Creation](https://docs.zapier.com/powered-by-zapier/zap-creation/quick-account-creation)
- [Zapier Sponsor User Automation](https://docs.zapier.com/powered-by-zapier/sponsor-user-automation/getting-started)
- [Zapier AI Zap Guesser](https://docs.zapier.com/powered-by-zapier/ai-workflows/zap-guesser)

---

## Executive Summary

CodeTether has **solid foundational infrastructure** for integrations:
- Webhook callbacks with retry support (3 attempts, exponential backoff)
- Email notifications with reply-to continuation  
- Bearer token and Keycloak OIDC authentication
- SSE streaming for real-time updates
- REST and JSON-RPC APIs
- User API keys with `ct_` prefix

However, comparing to Zapier's "Powered by Zapier" platform reveals **significant gaps**:

| Category | CodeTether | Zapier Standard | Gap Severity |
|----------|-----------|-----------------|--------------|
| API Simplicity | Complex A2A/JSON-RPC | Simple REST with OpenAPI | **High** |
| OAuth 2.0 | Keycloak only | Full OAuth 2.0 with scopes | **High** |
| Rate Limit Headers | None | `X-RateLimit-*` headers | **Medium** |
| Webhook Events | Completion only | Subscription-based events | **Medium** |
| Quick Account Creation | None | Frictionless signup flow | **Medium** |
| AI Workflow Suggestion | None | Zap Guesser API | **Low** |
| Sponsor/Embed Mode | None | Partner sponsors user costs | **High** |
| OpenAPI Spec | None | Full OpenAPI 3.1 | **High** |

---

## Gap 1: No Simple REST API for Automation Platforms

### Current State
CodeTether exposes the A2A Protocol which uses JSON-RPC 2.0:

```bash
# Current: Complex JSON-RPC
curl -X POST https://api.codetether.run/a2a/jsonrpc \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "jsonrpc": "2.0",
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"type": "text", "content": "Analyze this code"}]
      }
    },
    "id": "1"
  }'
```

### What Automation Platforms Expect
Simple REST endpoints with intuitive payloads:

```bash
# Expected: Simple REST
curl -X POST https://api.codetether.run/v1/tasks \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "prompt": "Analyze this code",
    "callback_url": "https://hooks.zapier.com/...",
    "notify_email": "user@example.com"
  }'
```

### Gap
- **No `/v1/tasks` endpoint** for simple task creation
- **No simple prompt field** - requires understanding A2A message structure
- **Response format** is A2A protocol objects, not simple JSON

### Recommendation
Create a simplified "Automation API" layer:

```python
# POST /v1/automation/tasks
{
    "prompt": "string (required)",
    "callback_url": "string (optional)",
    "notify_email": "string (optional)",
    "priority": "integer (optional, default 0)",
    "metadata": "object (optional)",
    "model": "string (optional, e.g. 'claude-sonnet', 'gpt-4')"
}

# Response
{
    "task_id": "uuid",
    "run_id": "uuid",
    "status": "queued",
    "created_at": "ISO8601",
    "estimated_completion": "ISO8601 (optional)"
}
```

---

## Gap 2: No OpenAPI/Swagger Specification

### Current State
- API documented in markdown files
- No machine-readable spec
- No auto-generated client SDKs

### What Automation Platforms Expect
- **OpenAPI 3.x spec** at `/.well-known/openapi.json` or `/openapi.json`
- Auto-discovery of endpoints, parameters, response schemas
- Zapier/n8n can auto-generate integrations from OpenAPI specs

### Gap
Without OpenAPI, every automation platform integration must be hand-coded.

### Recommendation
1. Add OpenAPI spec generation (FastAPI supports this natively)
2. Expose at `/openapi.json` and `/.well-known/openapi.json`
3. Include authentication schemes in spec

---

## Gap 3: Limited Webhook Event Types

### Current State
Webhooks only fire on **task completion**:

```python
# Current webhook payload (hosted_worker.py:659-667)
payload = {
    'event': 'task_completed',
    'run_id': run_id,
    'task_id': task_id,
    'status': status,
    'result': result,
    'error': error,
    'timestamp': datetime.now(timezone.utc).isoformat(),
}
```

### What Automation Platforms Expect
Multiple event types for workflow branching:

| Event | Description | Use Case |
|-------|-------------|----------|
| `task.created` | Task was queued | Trigger follow-up workflows |
| `task.started` | Worker claimed task | Update status dashboards |
| `task.progress` | Intermediate output | Stream results to user |
| `task.completed` | Task finished successfully | **Currently supported** |
| `task.failed` | Task failed | Error handling workflows |
| `task.cancelled` | Task was cancelled | Cleanup workflows |
| `task.needs_input` | Agent needs user input | Human-in-the-loop |

### Gap
- Only `task_completed` event (covers both success and failure)
- No `task.started`, `task.progress`, `task.needs_input` events
- No webhook subscription management

### Recommendation
1. Add event type enum to webhook payloads
2. Allow subscribing to specific event types
3. Add webhook registration API:

```python
# POST /v1/webhooks
{
    "url": "https://hooks.zapier.com/...",
    "events": ["task.completed", "task.failed"],
    "secret": "optional HMAC secret"
}
```

---

## Gap 4: No Webhook Signature Verification

### Current State
Webhooks are sent without signatures. Recipients cannot verify authenticity.

### What Automation Platforms Expect
HMAC signatures for webhook verification (like Stripe, GitHub):

```http
POST /webhook HTTP/1.1
X-CodeTether-Signature: sha256=abc123...
X-CodeTether-Timestamp: 1234567890

{"event": "task.completed", ...}
```

### Gap
- No `X-CodeTether-Signature` header
- No timestamp for replay protection
- No webhook secret management

### Recommendation
1. Generate per-webhook secrets
2. Sign payloads with HMAC-SHA256
3. Include timestamp for replay protection
4. Document verification in multiple languages

---

## Gap 5: No Idempotency Support

### Current State
Repeated POST requests create duplicate tasks.

### What Automation Platforms Expect
Idempotency keys for safe retries:

```bash
curl -X POST https://api.codetether.run/v1/tasks \
  -H "Idempotency-Key: zapier-trigger-abc123" \
  -d '{"prompt": "..."}'
```

### Gap
If Zapier retries a failed webhook, it creates duplicate tasks.

### Recommendation
1. Accept `Idempotency-Key` header
2. Store keys with 24h TTL
3. Return cached response for duplicate keys

---

## Gap 6: No Rate Limit Headers

### Current State
Rate limits exist but aren't communicated in responses.

### What Automation Platforms Expect
Standard rate limit headers:

```http
HTTP/1.1 200 OK
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1234567890
Retry-After: 60  (when rate limited)
```

### Gap
Automation platforms can't implement proper backoff without these headers.

### Recommendation
Add middleware to include rate limit headers on all responses.

---

## Gap 7: No Integration-Focused Documentation

### Current State
Documentation is developer/operator focused:
- A2A Protocol concepts
- Kubernetes deployment
- Keycloak configuration

### What Automation Platform Users Expect
- **Quick start for Zapier/n8n/Make**
- Copy-paste webhook URLs
- Example Zaps/workflows
- Troubleshooting common issues

### Gap
No dedicated "Integrations" documentation section.

### Recommendation
Create `/integrations/` docs section with:
- `zapier.md` - Step-by-step Zapier integration
- `n8n.md` - n8n workflow examples  
- `make.md` - Make (Integromat) scenarios
- `webhooks.md` - Generic webhook integration guide
- `api-keys.md` - API key management for automations

---

## Gap 8: Authentication Gaps for Automation

### Current State
- Bearer tokens via `A2A_AUTH_TOKENS` env var (shared)
- Keycloak OIDC (complex for automations)
- User API keys with `ct_` prefix (good!)

### What Automation Platforms Need
- **Per-integration API keys** with scoped permissions
- **OAuth 2.0** for Zapier/n8n native integrations
- **API key in query string** option (some platforms don't support headers well)

### Gap
- No OAuth 2.0 client credentials flow
- No scoped API keys (all keys have full access)
- No query string auth option

### Recommendation
1. Implement OAuth 2.0 client credentials for platform integrations
2. Add scope support to API keys: `tasks:read`, `tasks:write`, `webhooks:manage`
3. Support `?api_key=` query parameter (with appropriate warnings)

---

## Gap 9: No Polling Endpoint for Status

### Current State
Status checking requires JSON-RPC:

```bash
curl -X POST https://api.codetether.run/a2a/jsonrpc \
  -d '{"jsonrpc":"2.0","method":"tasks/get","params":{"id":"task-123"},"id":"1"}'
```

### What Automation Platforms Expect
Simple GET endpoint:

```bash
curl https://api.codetether.run/v1/tasks/task-123
```

### Gap
The REST binding exists at `/a2a/rest/tasks/{id}` but:
- Not documented prominently
- Returns A2A protocol format, not simple JSON

### Recommendation
Add `/v1/automation/tasks/{id}` with simple response:

```json
{
    "task_id": "task-123",
    "status": "completed",
    "result": "Summary of what the agent did...",
    "created_at": "2024-01-15T10:00:00Z",
    "completed_at": "2024-01-15T10:05:00Z"
}
```

---

## Gap 10: No "Powered by CodeTether" Partner Model

### What Zapier Offers
Zapier's "Powered by Zapier" allows partners to:
1. **Embed Zapier UI** - Pre-built workflow elements in partner's product
2. **Sponsor User Automation** - Partner pays for user's task usage
3. **Quick Account Creation** - Frictionless signup without leaving partner's app
4. **Zap Guesser AI** - Natural language → workflow suggestions

```bash
# Zapier's Zap Guesser API
POST https://api.zapier.com/v2/guess
{
  "description": "Save new leads from Facebook to Google Sheets"
}

# Returns suggested workflow with prefilled editor URL
{
  "title": "Save Facebook Lead Ads leads to Google Sheets",
  "steps": [...],
  "prefilled_url": "https://api.zapier.com/v1/embed/..."
}
```

### Current State
CodeTether has no equivalent partner/embed model.

### Gap
- No embeddable UI components
- No partner billing/sponsorship model
- No "Quick Account Creation" flow
- No AI-powered workflow suggestions

### Recommendation (Future)
Consider building "Powered by CodeTether" for partners who want to embed AI agent capabilities:
1. Embeddable task creation widget
2. Partner billing API (sponsor user tasks)
3. White-label agent execution

---

## Gap 11: No Zapier App in Zapier Directory

### Current State
Users must configure raw HTTP webhooks to connect CodeTether to Zapier.

### What Would Significantly Improve Adoption
A **native Zapier App** in the [Zapier App Directory](https://zapier.com/apps) with:

**Triggers:**
- "New Task Completed" - fires when an agent task finishes
- "Task Failed" - fires on task failure
- "Task Needs Input" - fires when agent requires human input

**Actions:**
- "Create Task" - submit a prompt to CodeTether
- "Get Task Status" - check task progress
- "Cancel Task" - cancel a running task

**Authentication:**
- OAuth 2.0 (required for public Zapier apps)

### Gap
No native Zapier integration - users must understand HTTP/webhooks.

### Zapier App Requirements (from their docs)
1. Must be a **public integration** in Zapier's App Directory
2. Must support **OAuth 2.0** authentication
3. Must have **OpenAPI spec** for auto-discovery
4. Must handle **rate limiting** with standard headers

---

## Gap 12: No Async Action Run Pattern

### What Zapier Implements
Zapier's Action Runs API uses an async pattern with polling:

```bash
# 1. Create action run (returns immediately)
POST /v2/action-runs
{
  "data": {
    "action": "example_core:Vn7xbE60",
    "authentication": "example_QVaAreV1",
    "inputs": {"email": "me@example.com"}
  }
}

# Response (immediate)
{
  "data": {
    "type": "run",
    "id": "123e4567-e89b-12d3-a456-426614174000"
  }
}

# 2. Poll for results
GET /v2/action-runs/123e4567-e89b-12d3-a456-426614174000
```

### Current State
CodeTether supports this pattern via:
- `POST /v1/opencode/codebases/{id}/tasks` (create)
- `GET /v1/opencode/tasks/{id}` (poll)

But the API is complex and not documented for this use case.

### Gap
The async pattern exists but:
- Not documented as a simple integration pattern
- Response format is complex (A2A protocol)
- No simple "run and poll" example

### Recommendation
Document the existing async pattern prominently with simple examples.

---

## Implementation Priority (Updated with Zapier Context)

| Gap | Effort | Impact | Priority |
|-----|--------|--------|----------|
| Gap 1: Simple REST API | Medium | High | **P0** |
| Gap 2: OpenAPI Spec | Low | High | **P0** |
| Gap 7: Integration Docs | Low | High | **P0** |
| Gap 8: OAuth 2.0 (full) | High | **Critical for Zapier** | **P0** |
| Gap 6: Rate Limit Headers | Low | Medium | **P1** |
| Gap 3: Webhook Events | Medium | Medium | **P1** |
| Gap 4: Webhook Signatures | Low | Medium | **P1** |
| Gap 5: Idempotency | Medium | Medium | **P2** |
| Gap 9: Simple Polling | Low | Medium | **P2** |
| Gap 12: Async Pattern Docs | Low | Medium | **P2** |
| Gap 11: Zapier App | High | Very High | **P3** |
| Gap 10: Partner Embed Model | Very High | Strategic | **Future** |

---

## Quick Wins (Can ship this week)

1. **Enable FastAPI's built-in OpenAPI** at `/openapi.json`
2. **Add rate limit headers** via middleware (Zapier expects `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`, `Retry-After`)
3. **Document the existing REST binding** (`/a2a/rest/tasks/{id}`)
4. **Create Zapier quick start guide** with existing webhook capabilities
5. **Add `X-Request-ID` header** to all responses for debugging

---

## What Zapier Requires for a Public App

To publish CodeTether as a Zapier App, we need:

| Requirement | Current State | Action Needed |
|-------------|---------------|---------------|
| OAuth 2.0 with authorization code flow | Keycloak (complex) | Add standard OAuth 2.0 |
| OpenAPI 3.x specification | None | Enable FastAPI's built-in |
| Rate limit headers | None | Add middleware |
| Webhook triggers | Partial (completion only) | Add event subscriptions |
| Idempotent actions | None | Add idempotency keys |
| Error responses in JSON API format | Partial | Standardize error format |

**Reference:** [Zapier Integration Publishing Requirements](https://docs.zapier.com/platform/publish/integration-publishing-requirements)

---

## Appendix A: Current Webhook Payload

```json
{
    "event": "task_completed",
    "run_id": "uuid",
    "task_id": "uuid", 
    "status": "completed|failed|cancelled",
    "result": "Summary text or null",
    "error": "Error message or null",
    "timestamp": "ISO8601"
}
```

This payload is **adequate but minimal**. Consider adding:
- `duration_seconds`
- `worker_id` (for debugging)
- `metadata` (user-provided context)
- `artifacts` (list of generated files/outputs)

---

## Appendix B: Zapier API Examples for Reference

### Zapier OAuth 2.0 Flow
```bash
# 1. Redirect user to authorize
https://api.zapier.com/v2/authorize
  ?response_type=code
  &client_id={CLIENT_ID}
  &redirect_uri={REDIRECT_URI}
  &scope=zap%20zap:write%20authentication
  &state={RANDOM_STRING}

# 2. Exchange code for token
POST https://zapier.com/oauth/token/
  -u {CLIENT_ID}:{CLIENT_SECRET}
  -d "grant_type=authorization_code&code={CODE}&redirect_uri={URI}"

# Response
{
  "access_token": "jk8s9dGJK39JKD93jkd03JD",
  "expires_in": 36000,
  "token_type": "Bearer",
  "scope": "zap zap:write authentication",
  "refresh_token": "9D9oz2ZzaouT12LpvklQwNBf6s4vva"
}
```

### Zapier Rate Limiting
- **60 requests/minute** per IP
- **150 requests/minute** per partner
- Returns `429 Too Many Requests` with 60s cooldown
- Headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`, `Retry-After`

### Zapier Quick Account Creation
```html
<zapier-workflow
  sign-up-email="user@example.com"
  sign-up-first-name="John"
  sign-up-last-name="Doe"
  client-id="YOUR_CLIENT_ID"
></zapier-workflow>
```

Users skip normal signup and go directly to workflow creation.
