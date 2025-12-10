---
title: Environment Variables
description: Complete environment variable reference
---

# Environment Variables

Complete reference of all AgentMesh environment variables.

See [Configuration](../getting-started/configuration.md) for detailed documentation.

## Core

| Variable | Default | Description |
|----------|---------|-------------|
| `A2A_HOST` | `0.0.0.0` | Server host |
| `A2A_PORT` | `8000` | Server port |
| `A2A_LOG_LEVEL` | `INFO` | Log level |
| `A2A_REDIS_URL` | `redis://localhost:6379` | Redis URL |

## Authentication

| Variable | Default | Description |
|----------|---------|-------------|
| `A2A_AUTH_ENABLED` | `false` | Enable auth |
| `A2A_AUTH_TOKENS` | — | Token list |
| `KEYCLOAK_URL` | — | Keycloak URL |
| `KEYCLOAK_REALM` | — | Realm |
| `KEYCLOAK_CLIENT_ID` | — | Client ID |
| `KEYCLOAK_CLIENT_SECRET` | — | Client secret |

## MCP

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_HTTP_ENABLED` | `true` | Enable MCP |
| `MCP_HTTP_PORT` | `9000` | MCP port |

## OpenCode Integration

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENCODE_HOST` | `localhost` | Host where OpenCode API runs (use `host.docker.internal` in Docker) |
| `OPENCODE_PORT` | `9777` | OpenCode API port |
| `OPENCODE_DB_PATH` | `./data/opencode.db` | SQLite database path |
