---
title: Policy Engine (OPA)
description: Centralized authorization with Open Policy Agent and Rego policies
---

# Policy Engine (OPA)

!!! info "v1.5.0"
    The OPA policy engine was introduced in v1.5.0. It provides centralized, declarative authorization across both the Python A2A Server and the Rust CodeTether Agent.

CodeTether uses [Open Policy Agent (OPA)](https://www.openpolicyagent.org/) as a centralized Policy Decision Point (PDP). Authorization decisions are written in the [Rego](https://www.openpolicyagent.org/docs/latest/policy-language/) policy language and evaluated either by an OPA sidecar (production) or in-process (development).

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Request Flow                             │
│                                                             │
│  Client → Auth (Bearer/JWT/API Key) → Policy Middleware     │
│                                        │                    │
│                          ┌─────────────▼──────────────┐     │
│                          │   OPA Policy Engine         │     │
│                          │  ┌───────────────────────┐  │     │
│                          │  │ authz.rego   (RBAC)   │  │     │
│                          │  │ api_keys.rego (scopes)│  │     │
│                          │  │ tenants.rego (isolate) │  │     │
│                          │  │ data.json   (roles)   │  │     │
│                          │  └───────────────────────┘  │     │
│                          └─────────────────────────────┘     │
│                                        │                    │
│                          Allow ────────┼──── Deny (403)     │
│                            │                                │
│                     Route Handler                           │
└─────────────────────────────────────────────────────────────┘
```

## How It Works

1. **Authentication** resolves the user identity (Keycloak JWT, self-issued JWT, or API key)
2. **Policy middleware** maps the request path + HTTP method to a permission string (e.g. `tasks:write`)
3. **OPA evaluates** the user's roles, scopes, and tenant against the required permission
4. The request is **allowed** or **denied with a 403**

## RBAC Roles

Five roles are defined with hierarchical permissions:

| Role | Description | Key Permissions |
|------|-------------|-----------------|
| **admin** | Full system access | All permissions including `admin:*` |
| **a2a-admin** | Alias for admin | Inherits all admin permissions |
| **operator** | Operations management | Read/write tasks, workers, sessions; monitor; execute agents |
| **editor** | Development access | Read/write tasks, codebases; execute agents; no worker mgmt |
| **viewer** | Read-only access | Read tasks, codebases, sessions, monitor |

Roles are assigned via Keycloak realm roles or self-service user registration.

### Permission Format

Permissions follow the pattern `resource:action`:

```
tasks:read        # Read tasks
codebases:write   # Create/update codebases
admin:access      # Access admin endpoints
agent:execute     # Trigger agent runs
workers:delete    # Remove workers
```

### Full Permission Matrix

| Resource | read | write | delete | execute | admin/access |
|----------|------|-------|--------|---------|--------------|
| tasks | viewer+ | editor+ | admin | editor+ | — |
| codebases | viewer+ | editor+ | admin | — | — |
| workers | viewer+ | operator+ | admin | — | — |
| sessions | viewer+ | editor+ | admin | — | — |
| monitor | viewer+ | operator+ | — | — | — |
| agent | viewer+ | editor+ | — | editor+ | — |
| admin | — | — | — | — | admin |
| ralph | viewer+ | editor+ | admin | — | — |
| mcp | viewer+ | editor+ | — | — | — |
| voice | viewer+ | editor+ | admin | — | — |
| analytics | viewer+ | admin | — | — | admin |
| email | operator+ | admin | — | — | admin |

## API Key Scope Enforcement

API keys (`ct_*` prefix) carry explicit scopes that further restrict access beyond the user's role:

```bash
# Create an API key with limited scopes
curl -X POST /v1/users/api-keys \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name": "CI Pipeline", "scopes": ["tasks:read", "tasks:write"]}'
```

Even if the user has an `editor` role, the API key can only perform actions within its granted scopes. Wildcard scopes are supported:

```json
{"scopes": ["tasks:*"]}  // All task operations
```

## Tenant Isolation

Multi-tenant deployments enforce strict resource isolation:

- Users can only access resources within their own tenant
- **Admin** role bypasses tenant restrictions for cross-tenant operations
- Tenant ID is extracted from the Keycloak JWT `iss` claim

## Policy Files

All policies live in the `policies/` directory:

| File | Purpose |
|------|---------|
| `data.json` | Role definitions and permission mappings |
| `authz.rego` | Main RBAC authorization rules |
| `api_keys.rego` | API key scope enforcement |
| `tenants.rego` | Tenant isolation and ownership checks |
| `authz_test.rego` | Unit tests for RBAC rules |
| `api_keys_test.rego` | Unit tests for scope enforcement |
| `tenants_test.rego` | Unit tests for tenant isolation |

### Testing Policies

```bash
# Run all 41 OPA unit tests
make policy-test

# Check policy syntax
make policy-check

# Run Python integration tests
OPA_LOCAL_MODE=true pytest tests/test_policy.py -v

# Run middleware path-matching tests
pytest tests/test_policy_middleware.py -v
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPA_URL` | `http://localhost:8181` | OPA sidecar HTTP address |
| `OPA_LOCAL_MODE` | `false` | Evaluate policies in-process (no sidecar needed) |
| `OPA_FAIL_OPEN` | `false` | Allow requests when OPA is unreachable (NOT recommended) |
| `OPA_CACHE_TTL` | `5.0` | Seconds to cache authorization decisions |
| `OPA_TIMEOUT` | `2.0` | HTTP timeout for OPA requests (seconds) |

### Development Mode

For local development, enable local mode to skip the OPA sidecar:

```bash
export OPA_LOCAL_MODE=true
python run_server.py run --port 8001
```

In local mode, policies are evaluated in-process using `policies/data.json`. This is functionally equivalent to the OPA sidecar but without the HTTP overhead.

### Production Mode (Kubernetes)

In production, OPA runs as a sidecar container alongside the A2A Server:

```yaml
# chart/a2a-server/values.yaml
opa:
  enabled: true
  image:
    repository: openpolicyagent/opa
    tag: latest
  resources:
    requests:
      memory: "128Mi"
      cpu: "100m"
    limits:
      memory: "256Mi"
      cpu: "200m"
```

The Helm chart automatically:

1. Deploys an OPA sidecar with the policy files mounted via ConfigMap
2. Configures the A2A Server to query OPA at `http://localhost:8181`
3. Adds health checks for the OPA sidecar

## Python Integration

### Protecting a Route with `require_permission`

```python
from a2a_server.policy import require_permission

@router.get("/tasks")
async def list_tasks(user=Depends(require_permission("tasks:read"))):
    # user is authenticated and authorized
    return await get_tasks(user)

@router.post("/tasks")
async def create_task(user=Depends(require_permission("tasks:write"))):
    return await create_task_for_user(user)
```

### Inline Policy Check

```python
from a2a_server.policy import enforce_policy

async def update_task(task_id: str, user: dict):
    task = await get_task(task_id)
    await enforce_policy(user, "tasks:write", resource={
        "type": "task",
        "id": task_id,
        "owner_id": task.owner_id,
        "tenant_id": task.tenant_id,
    })
    # Proceeds only if allowed; raises HTTPException(403) otherwise
```

### Centralized Middleware

The `PolicyAuthorizationMiddleware` automatically enforces authorization on ~120 endpoints by mapping URL paths to permission strings. Routes that are intentionally public (health checks, auth endpoints, discovery) or already protected by existing dependencies are skipped.

## Rust Integration (CodeTether Agent)

The Rust agent includes a compiled-in copy of `policies/data.json` for zero-dependency local evaluation:

```rust
use crate::server::policy::{PolicyUser, check_policy, enforce_policy};

let user = PolicyUser {
    user_id: "user-123".to_string(),
    roles: vec!["editor".to_string()],
    tenant_id: Some("tenant-1".to_string()),
    scopes: vec![],
    auth_source: "keycloak".to_string(),
};

// Check without raising
let allowed = check_policy(&user, "tasks:write", None).await;

// Enforce — returns Err(StatusCode::FORBIDDEN) on denial
enforce_policy(&user, "admin:access", None).await?;
```

The Axum middleware maps all agent endpoints to OPA permission strings and enforces authorization after bearer token validation.

## Adding a New Permission

1. Add the permission to the appropriate role(s) in `policies/data.json`
2. Add a test in the relevant `*_test.rego` file
3. Run `make policy-test` to verify
4. If it's a new endpoint, add a path rule in `a2a_server/policy_middleware.py`
5. Add a test in `tests/test_policy_middleware.py`

## Health Check

The OPA health status is included in the server's `/health` endpoint:

```json
{
  "status": "healthy",
  "opa": {
    "mode": "sidecar",
    "healthy": true,
    "url": "http://localhost:8181"
  }
}
```
