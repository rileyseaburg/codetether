---
title: Keycloak Setup
description: Configure Keycloak OIDC authentication
---

# Keycloak Setup

Integrate CodeTether with Keycloak for enterprise SSO.

## Prerequisites

- Keycloak server
- Admin access to create clients

## Configuration

### Option A: Use the Keycloak UI

1. Create a client in Keycloak
2. Set environment variables:

```bash
export KEYCLOAK_URL=https://auth.example.com
export KEYCLOAK_REALM=myrealm
export KEYCLOAK_CLIENT_ID=codetether
export KEYCLOAK_CLIENT_SECRET=your-secret
```

3. Restart CodeTether

### Option B: Create/update the client via CLI (recommended)

This repo includes a helper script that uses the Keycloak Admin CLI (`kcadm.sh`) to upsert an OIDC client with:

- Authorization Code flow enabled (works with browser session + PKCE)
- Direct Access Grants enabled (used by `/v1/auth/login` password flow)
- Redirect URIs for the local session test script

#### Run it

Set the required environment variables and run:

```bash
make keycloak-client
```

#### Required environment variables

```bash
export KEYCLOAK_URL=https://auth.example.com
export KEYCLOAK_REALM=myrealm
export KEYCLOAK_CLIENT_ID=a2a-monitor

# Keycloak admin creds (used only for provisioning)
export KEYCLOAK_ADMIN_USERNAME=admin
export KEYCLOAK_ADMIN_PASSWORD=your-admin-password
```

#### Optional knobs

```bash
# Defaults are suitable for scripts/test_api_keycloak_session.py
export KEYCLOAK_REDIRECT_URIS="http://127.0.0.1:8765/*,http://localhost:8765/*"
export KEYCLOAK_WEB_ORIGINS="http://127.0.0.1:8765,http://localhost:8765"

# Set to true if you want a public client (no client secret)
export KEYCLOAK_PUBLIC_CLIENT=false
```

After the script runs, it prints `KEYCLOAK_CLIENT_SECRET=...` (for confidential clients). Copy that into your environment / `.env` / Helm values.

See [Configuration](../getting-started/configuration.md) for all options.
