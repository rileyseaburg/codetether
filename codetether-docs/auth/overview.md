---
title: Authentication Overview
description: Authentication options in CodeTether
---

# Authentication

CodeTether has two layers of authentication:

1. **Agent-level** (Rust, mandatory) — Bearer token auth built into the agent runtime. Cannot be disabled.
2. **Server-level** (Python, configurable) — API tokens or Keycloak OIDC for the A2A server.

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
