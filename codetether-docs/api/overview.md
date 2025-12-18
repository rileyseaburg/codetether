---
title: API Overview
description: CodeTether Server API reference
---

# API Overview

CodeTether Server exposes multiple API endpoints for different purposes.

## Endpoint Summary

| Endpoint | Port | Protocol | Description |
|----------|------|----------|-------------|
| `/v1/a2a` | 8000 | JSON-RPC 2.0 | A2A Protocol - agent-to-agent communication (alias: `POST /`) |
| `/v1/opencode/*` | 8000 | REST | OpenCode integration - codebase & session management |
| `/v1/monitor/*` | 8000 | REST | Monitoring - agents, messages, stats |
| `/v1/auth/*` | 8000 | REST | Authentication - tokens, sessions |
| `/mcp/v1/*` | 9000 | JSON-RPC | MCP Protocol - tool integration |
| `/.well-known/agent-card.json` | 8000 | REST | A2A agent discovery |
| `/health` | 8000 | REST | Health check |

## Base URLs

```
# A2A Protocol (JSON-RPC)
POST https://codetether.example.com/v1/a2a

# REST APIs
GET/POST https://codetether.example.com/v1/opencode/...
GET/POST https://codetether.example.com/v1/monitor/...

# MCP Protocol
POST https://codetether.example.com:9000/mcp/v1/rpc

# MCP Protocol (when exposed via ingress)
POST https://codetether.example.com/mcp/v1/rpc
```

## Authentication

### Bearer Token

```bash
curl -X POST https://codetether.example.com/v1/a2a \
  -H "Authorization: Bearer your-api-token" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", ...}'
```

### Keycloak OIDC

If Keycloak is configured, obtain a token first:

```bash
# Get access token
TOKEN=$(curl -s -X POST "https://auth.example.com/realms/myrealm/protocol/openid-connect/token" \
  -d "client_id=codetether" \
  -d "client_secret=your-secret" \
  -d "grant_type=client_credentials" | jq -r '.access_token')

# Use token
curl -X POST https://codetether.example.com/v1/a2a \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", ...}'
```

## Common Response Codes

| Code | Description |
|------|-------------|
| `200` | Success |
| `400` | Bad request - invalid parameters |
| `401` | Unauthorized - missing or invalid token |
| `403` | Forbidden - insufficient permissions |
| `404` | Not found - resource doesn't exist |
| `500` | Server error |
| `503` | Service unavailable - dependency not ready |

## API Sections

<div class="grid cards" markdown>

-   :material-protocol:{ .lg .middle } __JSON-RPC Methods__

    A2A Protocol JSON-RPC methods for agent communication

    [:octicons-arrow-right-24: JSON-RPC Reference](jsonrpc.md)

-   :material-api:{ .lg .middle } __REST Endpoints__

    REST API for monitoring, health, and management

    [:octicons-arrow-right-24: REST Reference](rest.md)

-   :material-code-braces:{ .lg .middle } __OpenCode API__

    Codebase registration, sessions, and AI coding agents

    [:octicons-arrow-right-24: OpenCode Reference](opencode.md)

-   :material-broadcast:{ .lg .middle } __SSE Events__

    Server-Sent Events for real-time streaming

    [:octicons-arrow-right-24: SSE Reference](sse.md)

</div>
