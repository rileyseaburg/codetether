---
title: Environment Variables
description: Complete environment variable reference
---

# Environment Variables

Complete reference of all CodeTether environment variables.

See [Configuration](../getting-started/configuration.md) for detailed documentation.

## Core

| Variable | Default | Description |
|----------|---------|-------------|
| `A2A_HOST` | `0.0.0.0` | Server host |
| `A2A_PORT` | `8000` | Server port |
| `A2A_LOG_LEVEL` | `INFO` | Log level |

## Database & Storage

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | — | PostgreSQL connection URL for durable persistence. Format: `postgresql://user:password@host:port/database`. When set, workers, codebases, tasks, and sessions survive server restarts and work across replicas. |
| `A2A_DATABASE_URL` | — | Alias for `DATABASE_URL` |
| `A2A_REDIS_URL` | `redis://localhost:6379` | Redis URL (shared state for multi-replica deployments; used by task queues and CodeTether worker/session sync) |
| `OPENCODE_DB_PATH` | `./data/agent.db` | SQLite database path for CodeTether codebases/tasks registry (fallback when PostgreSQL not configured) |

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

## CodeTether Integration

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENCODE_HOST` | `localhost` | Host where CodeTether API runs (use `host.docker.internal` in Docker) |
| `OPENCODE_PORT` | `9777` | CodeTether API port |

## Worker SSE Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `WORKER_SSE_ENABLED` | `true` | Enable SSE task stream endpoint |
| `WORKER_SSE_KEEPALIVE` | `30` | Keepalive interval in seconds |
| `WORKER_SSE_TIMEOUT` | `300` | Worker idle timeout in seconds |

## Agent Worker (Remote Workers)

| Variable | Default | Description |
|----------|---------|-------------|
| `A2A_SERVER_URL` | — | CodeTether server URL (required) |
| `A2A_WORKER_NAME` | hostname | Worker identifier |
| `A2A_POLL_INTERVAL` | `5` | Task polling interval in seconds (fallback for SSE) |
| `A2A_OPENCODE_STORAGE_PATH` | auto-detect | Override CodeTether storage directory |
| `A2A_SESSION_MESSAGE_SYNC_MAX_SESSIONS` | `3` | Recent sessions to sync messages for |
| `A2A_SESSION_MESSAGE_SYNC_MAX_MESSAGES` | `100` | Recent messages per session to sync |

## Agent Discovery (v1.2.2+)

| Variable | Default | Description |
|----------|---------|-------------|
| `A2A_AGENT_NAME` | worker name | Agent routing role for `send_to_agent` |
| `A2A_AGENT_DESCRIPTION` | auto-generated | Human-readable agent description |
| `A2A_AGENT_URL` | server URL | URL where agent can be reached |
| `A2A_AGENT_DISCOVERY_MAX_AGE` | `120` | TTL in seconds for stale agent filtering (server-side) |

!!! note "Role vs Name"
    The `A2A_AGENT_NAME` sets the **routing role** (e.g., `code-reviewer`). The full discovery name is auto-generated as `role:hostname:worker_id` to ensure uniqueness across multiple workers with the same role.
