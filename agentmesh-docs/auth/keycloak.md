---
title: Keycloak Setup
description: Configure Keycloak OIDC authentication
---

# Keycloak Setup

Integrate AgentMesh with Keycloak for enterprise SSO.

## Prerequisites

- Keycloak server
- Admin access to create clients

## Configuration

1. Create a client in Keycloak
2. Set environment variables:

```bash
export KEYCLOAK_URL=https://auth.example.com
export KEYCLOAK_REALM=myrealm
export KEYCLOAK_CLIENT_ID=agentmesh
export KEYCLOAK_CLIENT_SECRET=your-secret
```

3. Restart AgentMesh

See [Configuration](../getting-started/configuration.md) for all options.
