---
title: Authentication Overview
description: Authentication options in CodeTether
---

# Authentication

CodeTether supports multiple authentication methods.

## Options

1. **API Tokens** - Simple bearer token authentication
2. **Keycloak OIDC** - Enterprise SSO integration

## Quick Setup

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
