---
title: Configuration
description: Configure CodeTether Server with environment variables
---

# Configuration

CodeTether Server is configured primarily through environment variables, making it easy to deploy in containers and Kubernetes.

## Quick Reference

```bash
# Core Server
export A2A_HOST=0.0.0.0
export A2A_PORT=8000
export A2A_LOG_LEVEL=INFO

# Agent Identity
export A2A_AGENT_NAME="My Agent"
export A2A_AGENT_DESCRIPTION="Production agent server"

# Redis (for distributed workers)
export A2A_REDIS_URL=redis://localhost:6379

# Authentication
export A2A_AUTH_ENABLED=true
export A2A_AUTH_TOKENS="admin:secret-token-1,worker:secret-token-2"

# Keycloak OIDC
export KEYCLOAK_URL=https://auth.example.com
export KEYCLOAK_REALM=myrealm
export KEYCLOAK_CLIENT_ID=codetether
export KEYCLOAK_CLIENT_SECRET=your-secret

# MCP Server
export MCP_HTTP_ENABLED=true
export MCP_HTTP_HOST=0.0.0.0
export MCP_HTTP_PORT=9000

# CodeTether Integration
export OPENCODE_DB_PATH=/data/agent.db
export OPENCODE_HOST=localhost
export OPENCODE_PORT=9777

# LiveKit (for media)
export LIVEKIT_URL=wss://live.example.com
export LIVEKIT_API_KEY=your-api-key
export LIVEKIT_API_SECRET=your-api-secret

# MinIO (for artifacts)
export MINIO_ENDPOINT=minio.example.com:9000
export MINIO_ACCESS_KEY=your-access-key
export MINIO_SECRET_KEY=your-secret-key
export MINIO_BUCKET=codetether
export MINIO_SECURE=true
```

## Configuration Categories

### Core Server Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `A2A_HOST` | `0.0.0.0` | Host to bind the server to |
| `A2A_PORT` | `8000` | Port for the A2A API |
| `A2A_LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |

### Agent Identity

| Variable | Default | Description |
|----------|---------|-------------|
| `A2A_AGENT_NAME` | `A2A Server` | Name shown in agent card |
| `A2A_AGENT_DESCRIPTION` | — | Description of the agent's capabilities |
| `A2A_AGENT_ORG` | `A2A Server` | Organization name |
| `A2A_AGENT_ORG_URL` | GitHub URL | Organization URL |

### Redis Configuration

Redis is required for distributed workers and task queuing.

| Variable | Default | Description |
|----------|---------|-------------|
| `A2A_REDIS_URL` | `redis://localhost:6379` | Redis connection URL |

!!! tip "Redis URL Format"
    ```
    redis://[[username]:[password]@]host[:port][/database]
    ```

    Examples:
    ```
    redis://localhost:6379
    redis://:password@redis.example.com:6379/0
    redis://user:pass@redis-cluster.example.com:6379
    ```

### Authentication

#### Token Authentication

| Variable | Default | Description |
|----------|---------|-------------|
| `A2A_AUTH_ENABLED` | `false` | Enable token authentication |
| `A2A_AUTH_TOKENS` | — | Comma-separated `name:token` pairs |

Example:
```bash
export A2A_AUTH_ENABLED=true
export A2A_AUTH_TOKENS="admin:abc123,worker:def456,readonly:xyz789"
```

#### Keycloak OIDC

| Variable | Default | Description |
|----------|---------|-------------|
| `KEYCLOAK_URL` | — | Keycloak server URL |
| `KEYCLOAK_REALM` | — | Keycloak realm name |
| `KEYCLOAK_CLIENT_ID` | — | OIDC client ID |
| `KEYCLOAK_CLIENT_SECRET` | — | OIDC client secret |
| `KEYCLOAK_ADMIN_USERNAME` | — | Admin username (for user management) |
| `KEYCLOAK_ADMIN_PASSWORD` | — | Admin password |

### MCP Server

The MCP (Model Context Protocol) server provides tool integration.

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_HTTP_ENABLED` | `true` | Enable MCP HTTP server |
| `MCP_HTTP_HOST` | `0.0.0.0` | MCP server host |
| `MCP_HTTP_PORT` | `9000` | MCP server port |

### CodeTether Integration

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENCODE_HOST` | `localhost` | Host where CodeTether API is running |
| `OPENCODE_PORT` | `9777` | CodeTether API port |
| `OPENCODE_DB_PATH` | `./data/agent.db` | SQLite database for CodeTether sessions |

!!! tip "Docker Container Configuration"
    When running CodeTether in Docker and connecting to CodeTether on your host:

    - **Docker Desktop (Mac/Windows)**: Use `OPENCODE_HOST=host.docker.internal`
    - **Linux**: Use `--add-host=host.docker.internal:host-gateway` and `OPENCODE_HOST=host.docker.internal`
    - **Alternative**: Use your host machine's actual IP address

### Database

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | — | PostgreSQL connection URL for durable persistence. Format: `postgresql://user:password@host:port/database`. When set, workers, codebases, tasks, and sessions survive server restarts and work across replicas. |
| `A2A_DATABASE_URL` | — | Alias for `DATABASE_URL` |
| `MONITOR_DB_PATH` | `./data/monitor.db` | SQLite database for monitoring data (fallback when PostgreSQL not configured) |
| `SESSIONS_DB_PATH` | — | Database path for session persistence |

!!! tip "PostgreSQL Connection URL Format"
    ```
    postgresql://[username]:[password]@host[:port]/database
    ```

    Examples:
    ```
    postgresql://postgres:secret@localhost:5432/codetether
    postgresql://user:pass@db.example.com:5432/a2a_server
    ```

!!! info "Storage Priority"
    CodeTether uses a tiered storage approach:

    1. **PostgreSQL** (primary) - Durable persistence across restarts and replicas
    2. **Redis** - Fast shared state for multi-replica deployments
    3. **In-memory** - Single-instance fallback when neither is configured

### LiveKit Media

For voice/video agent interactions.

| Variable | Default | Description |
|----------|---------|-------------|
| `LIVEKIT_URL` | — | LiveKit server WebSocket URL |
| `LIVEKIT_API_KEY` | — | LiveKit API key |
| `LIVEKIT_API_SECRET` | — | LiveKit API secret |

### MinIO Object Storage

For storing large artifacts and files.

| Variable | Default | Description |
|----------|---------|-------------|
| `MINIO_ENDPOINT` | — | MinIO server endpoint |
| `MINIO_ACCESS_KEY` | — | MinIO access key |
| `MINIO_SECRET_KEY` | — | MinIO secret key |
| `MINIO_BUCKET` | `a2a-monitor` | Default bucket name |
| `MINIO_SECURE` | `false` | Use HTTPS for MinIO |

### Worker Configuration

For distributed agent workers:

| Variable | Default | Description |
|----------|---------|-------------|
| `A2A_SERVER_URL` | `https://api.codetether.run` | Server URL to connect to |
| `A2A_WORKER_NAME` | hostname | Worker identifier |
| `A2A_POLL_INTERVAL` | `5` | Task polling interval (seconds) |

## Configuration Files

### `.env` File

Create a `.env` file in the project root:

```bash
# .env
A2A_PORT=8000
A2A_AGENT_NAME=Production Agent
A2A_REDIS_URL=redis://redis:6379
A2A_AUTH_ENABLED=true
KEYCLOAK_URL=https://auth.example.com
KEYCLOAK_REALM=production
KEYCLOAK_CLIENT_ID=codetether
```

### Kubernetes ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: codetether-config
data:
  A2A_HOST: "0.0.0.0"
  A2A_PORT: "8000"
  A2A_LOG_LEVEL: "INFO"
  A2A_REDIS_URL: "redis://redis:6379"
  MCP_HTTP_ENABLED: "true"
  MCP_HTTP_PORT: "9000"
```

### Kubernetes Secret

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: codetether-secrets
type: Opaque
stringData:
  A2A_AUTH_TOKENS: "admin:super-secret-token"
  KEYCLOAK_CLIENT_SECRET: "your-client-secret"
  MINIO_SECRET_KEY: "your-minio-secret"
```

## Validation

CodeTether validates configuration on startup. Check the logs for any configuration issues:

```bash
codetether serve --port 8000
# INFO: Configuration validated
# INFO: Redis connection: OK
# INFO: Keycloak: disabled
# INFO: MCP Server: enabled on port 9000
```

## Next Steps

- [Quick Start](quickstart.md) — Run your first agent
- [Keycloak Setup](../auth/keycloak.md) — Configure OIDC authentication
- [Kubernetes Deployment](../deployment/kubernetes.md) — Deploy to production
