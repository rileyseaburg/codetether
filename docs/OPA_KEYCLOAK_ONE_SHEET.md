# OPA + Keycloak Authorization — One Sheet

> **What:** Centralized RBAC authorization using Open Policy Agent (OPA) with Keycloak as the identity provider.
> **Why:** Declarative, auditable access control without scattering `if user.role == "admin"` checks across your codebase.

---

## Architecture

```
┌──────────┐      JWT (OIDC)     ┌───────────────┐     HTTP POST      ┌─────────┐
│ Keycloak │ ──────────────────▶│  Your Service │ ──────────────────▶│   OPA   │
│  (IdP)   │  access_token       │  (FastAPI)    │  /v1/data/authz/   │ sidecar │
└──────────┘  with roles         │               │◀───────────────── │         │
                                 │  Middleware   │  { "result": T/F } │  Rego   │
                                 └───────────────┘                    │ policies│
                                                                      └─────────┘
```

1. **Keycloak** authenticates users and issues JWTs containing realm roles (`admin`, `editor`, `viewer`, etc.)
2. **Your service** validates the JWT, extracts `user_id`, `roles`, `tenant_id`
3. **OPA sidecar** (or local mode) evaluates Rego policies against the request and returns allow/deny

---

## How It Works — 3 Layers

### Layer 1: Rego Policies (the rules)

Policies live in `policies/` and are loaded into OPA at startup.

| File | Purpose |
|------|---------|
| `authz.rego` | Core RBAC — maps roles → permissions, evaluates `allow` |
| `api_keys.rego` | Scope enforcement for API key auth (wildcards supported) |
| `tenants.rego` | Tenant isolation — users can only access their own tenant's resources |
| `data.json` | Role definitions and permission mappings (loaded as OPA data) |

**Core decision logic** (`authz.rego`):
```rego
package authz

default allow := false

# Public endpoints are always allowed
allow if { input.action in data.public_endpoints }

# Role-based: user's roles grant the requested permission
allow if { input.action in role_permissions }
```

### Layer 2: Middleware (automatic enforcement)

A single Starlette middleware intercepts every HTTP request, matches it against a route table, and enforces the corresponding permission — no per-endpoint code changes needed.

```python
# policy_middleware.py — route → permission mapping (excerpt)
_RULES = [
    (r"^/health$",          None,       ""),              # public, skip auth
    (r"^/v1/agent/tasks$",  {"POST"},   "tasks:write"),   # requires tasks:write
    (r"^/v1/agent/tasks",   {"GET"},    "tasks:read"),    # requires tasks:read
    (r"^/v1/admin/",        None,       ""),              # already has its own auth
    ...
]
```

Rules are evaluated top-to-bottom, first match wins. Empty permission (`""`) = skip auth.

### Layer 3: Python Client (programmatic checks)

For resource-level checks beyond what middleware catches:

```python
from a2a_server.policy import require_permission, enforce_policy

# Option A: FastAPI dependency (decorative)
@router.get("/tasks")
async def list_tasks(user=Depends(require_permission("tasks:read"))):
    ...

# Option B: Inline enforcement (imperative)
async def update_task(task_id: str, user: dict):
    await enforce_policy(user, "tasks:write", resource={
        "type": "task",
        "id": task_id,
        "owner_id": task.owner_id,
        "tenant_id": task.tenant_id,
    })
```

---

## OPA Input Schema

Every policy decision receives this JSON:

```json
{
  "input": {
    "user": {
      "user_id": "uuid-here",
      "roles": ["editor"],
      "tenant_id": "tenant-123",
      "scopes": [],
      "auth_source": "keycloak"
    },
    "action": "tasks:write",
    "resource": {
      "type": "task",
      "id": "task-456",
      "owner_id": "uuid-owner",
      "tenant_id": "tenant-123"
    }
  }
}
```

| Field | Source | Notes |
|-------|--------|-------|
| `user.roles` | Keycloak JWT `realm_access.roles` | Or `["editor"]` default for self-service users |
| `user.auth_source` | Detected automatically | `"keycloak"`, `"api_key"`, or `"self-service"` |
| `user.scopes` | API key record | Only populated for API key auth |
| `resource.*` | Your code | Optional — only needed for resource-level checks |

---

## RBAC Roles

Hierarchy: **admin** > **operator** > **editor** > **viewer**

| Role | Description | Example Permissions |
|------|-------------|---------------------|
| `admin` | Full system access | `admin:access`, `tasks:*`, `codebases:*`, everything |
| `a2a-admin` | Keycloak alias | Inherits all `admin` permissions |
| `operator` | Ops management | `tasks:read/write`, `workers:read/write`, `monitor:*` |
| `editor` | Standard user | `tasks:read/write`, `codebases:read/write`, `sessions:*` |
| `viewer` | Read-only | `tasks:read`, `codebases:read`, `monitor:read` |
| `a2a-user` | Keycloak alias | Inherits all `editor` permissions |
| `a2a-agent` | Service accounts | `tasks:read/write/execute`, `sessions:*`, `voice:*` |

Permissions follow `resource:action` format: `tasks:read`, `codebases:write`, `admin:access`.

---

## Deployment Modes

### Mode 1: OPA Sidecar (Production)

OPA runs as a sidecar container alongside your app. Policies are mounted via ConfigMap.

```yaml
# Helm values
opa:
  enabled: true    # deploys OPA sidecar + ConfigMap

# Environment
OPA_URL=http://localhost:8181      # sidecar is on localhost
OPA_ENABLED=true
```

**Kubernetes ConfigMap** auto-bundles all `.rego` files and `data.json`:
```yaml
# chart/templates/opa-configmap.yaml
data:
  data.json: |- ...
  authz.rego: |- ...
  api_keys.rego: |- ...
  tenants.rego: |- ...
```

### Mode 2: Local / Dev (No Sidecar)

Evaluates the same policy logic in-process — no OPA container needed.

```bash
OPA_LOCAL_MODE=true    # evaluate policies in Python
OPA_ENABLED=true
```

### Master Kill Switch

```bash
OPA_ENABLED=false    # disables ALL policy enforcement (emergency use only)
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPA_ENABLED` | `true` | Master toggle for all policy enforcement |
| `OPA_URL` | `http://localhost:8181` | OPA sidecar address |
| `OPA_LOCAL_MODE` | `false` | Evaluate policies in-process (no sidecar needed) |
| `OPA_FAIL_OPEN` | `false` | If OPA is unreachable: `false` = deny, `true` = allow |
| `OPA_CACHE_TTL` | `5.0` | Decision cache TTL in seconds (0 = disabled) |
| `OPA_TIMEOUT` | `2.0` | HTTP request timeout to OPA (seconds) |
| `DEFAULT_USER_ROLE` | `editor` | Fallback role for users with no explicit assignment |
| `KEYCLOAK_URL` | — | Keycloak base URL (e.g. `https://auth.example.com`) |
| `KEYCLOAK_REALM` | — | Keycloak realm name |
| `KEYCLOAK_CLIENT_ID` | — | OIDC client ID |
| `KEYCLOAK_CLIENT_SECRET` | — | OIDC client secret |

---

## Keycloak Setup

1. **Create a realm** (e.g. `my-service`)
2. **Create realm roles**: `admin`, `operator`, `editor`, `viewer` (or use `a2a-admin`, `a2a-user` aliases)
3. **Create an OIDC client** with:
   - Access Type: `confidential`
   - Valid Redirect URIs: your app's callback URL
   - Enable "Service Accounts" if you need machine-to-machine auth
4. **Assign roles** to users in Keycloak — they appear in the JWT under `realm_access.roles`
5. **Set env vars**: `KEYCLOAK_URL`, `KEYCLOAK_REALM`, `KEYCLOAK_CLIENT_ID`, `KEYCLOAK_CLIENT_SECRET`

---

## Adapting for Your Service

### Step 1: Define your permissions

Edit `policies/data.json` — add/remove permissions for each role:

```json
{
  "roles": {
    "editor": {
      "permissions": ["invoices:read", "invoices:write", "reports:read"]
    }
  }
}
```

### Step 2: Map your routes

Add entries to the route table in your middleware:

```python
_RULES = [
    (r"^/api/invoices$",   {"GET"},    "invoices:read"),
    (r"^/api/invoices$",   {"POST"},   "invoices:write"),
    (r"^/api/invoices/",   {"DELETE"}, "invoices:delete"),
    (r"^/api/reports",     {"GET"},    "reports:read"),
]
```

### Step 3: Add the middleware

```python
from policy_middleware import PolicyAuthorizationMiddleware

app = FastAPI()
app.add_middleware(PolicyAuthorizationMiddleware)
```

### Step 4: Deploy OPA

**Docker Compose:**
```yaml
services:
  opa:
    image: openpolicyagent/opa:latest
    command: ["run", "--server", "--addr", "0.0.0.0:8181", "/policies"]
    volumes:
      - ./policies:/policies
```

**Kubernetes (Helm):**
```yaml
opa:
  enabled: true
# Policies are mounted from ConfigMap automatically
```

---

## Testing Policies

```bash
# Run all OPA policy tests
opa test policies/ -v

# Test a specific decision manually
curl -X POST http://localhost:8181/v1/data/authz/allow \
  -H 'Content-Type: application/json' \
  -d '{
    "input": {
      "user": {"user_id": "u1", "roles": ["editor"], "tenant_id": "t1", "scopes": [], "auth_source": "keycloak"},
      "action": "tasks:read",
      "resource": {}
    }
  }'
# → {"result": true}

# Python integration tests
python -m pytest tests/test_policy.py tests/test_policy_middleware.py -v
```

---

## Decision Flow Summary

```
Request arrives
    │
    ▼
Middleware matches path → permission string
    │
    ├─ "" (empty) → SKIP (public or already protected)
    │
    ├─ No match → PASS THROUGH
    │
    └─ "tasks:write" → Resolve user from JWT
                            │
                            ├─ No user → 401
                            │
                            └─ OPA check(user, "tasks:write")
                                    │
                                    ├─ allowed → proceed to handler
                                    │
                                    └─ denied → 403
```
