---
title: Authentication & Authorization Overview
description: Authentication and authorization options in CodeTether
---

# Authentication & Authorization

CodeTether has three security layers:

1. **Authentication (Agent)** — Mandatory Bearer token auth in the Rust agent runtime. Cannot be disabled.
2. **Authentication (Server)** — API tokens or Keycloak OIDC for the Python A2A server.
3. **Authorization (OPA Policy Engine)** — Centralized RBAC + scope enforcement via Open Policy Agent. Applies to both Python and Rust.

## Agent Authentication (Mandatory)

The CodeTether Agent (v1.1.0+) enforces Bearer token authentication on every endpoint except `/health`. This is a compile-time guarantee — there is no configuration flag to disable it.

```bash
# Set a fixed token
export CODETETHER_AUTH_TOKEN="my-secure-token"
codetether serve --port 4096

# Or let the agent auto-generate one (logged at startup)
codetether serve --port 4096
```

All requests must include:
```
Authorization: Bearer <token>
```

See [Security Features](../features/security.md) for full details on the agent's security model.

## Server Authentication Options

1. **API Tokens** - Simple bearer token authentication
2. **Keycloak OIDC** - Enterprise SSO integration

### API Tokens

```bash
export A2A_AUTH_ENABLED=true
export A2A_AUTH_TOKENS="admin:your-secret-token"
```

### Keycloak

```bash
export KEYCLOAK_URL=https://auth.example.com
export KEYCLOAK_REALM=myrealm
export KEYCLOAK_CLIENT_ID=codetether
```

See [Keycloak Setup](keycloak.md) for full configuration.

## Authorization (OPA Policy Engine)

Beyond authentication, CodeTether enforces fine-grained authorization using [Open Policy Agent (OPA)](https://www.openpolicyagent.org/):

- **5 RBAC roles**: admin, a2a-admin, operator, editor, viewer
- **Resource-level permissions**: `tasks:read`, `codebases:write`, `admin:access`, etc.
- **API key scope enforcement**: Keys are restricted to their granted scopes
- **Tenant isolation**: Users can only access resources in their own tenant
- **Centralized middleware**: ~120 endpoints secured by path→permission mapping

```bash
# Enable local policy evaluation (no OPA sidecar needed)
export OPA_LOCAL_MODE=true

# Or connect to OPA sidecar (production)
export OPA_URL=http://localhost:8181
```

See [Policy Engine (OPA)](policy-engine.md) for full configuration and role details.
