---
title: Architecture
description: CodeTether Server architecture overview
---

# Architecture

CodeTether Server is designed as a modular, scalable system for running AI agents in production.

## High-Level Architecture

```mermaid
graph TB
    subgraph Clients
        Web[Web Dashboard]
        CLI[CLI / SDK]
        Agents[External Agents]
    end

    subgraph Edge[Ingress / DNS]
        MKT[codetether.run]
        DOCS[docs.codetether.run]
        APIHOST[api.codetether.run]
    end

    subgraph "Cluster / Services"
        Marketing["Marketing Site<br/>(Next.js)<br/>Port 3000"]
        DocsSite["Docs Site<br/>(MkDocs)<br/>Port 80"]

        subgraph "CodeTether API"
            API["FastAPI App<br/>Port 8000"]
            A2A["A2A JSON-RPC Handler<br/>POST /v1/a2a (alias: /)"]
            Monitor["Monitor API<br/>/v1/monitor/*"]
            OpenCode["OpenCode Bridge<br/>/v1/opencode/*"]
        end

        MCP["MCP HTTP Server<br/>Port 9000<br/>/mcp/v1/*"]

        Redis[("Redis<br/>Pub/Sub + task/state")]
    end

    subgraph "Workers (systemd / containers)"
        W1["Worker 1<br/>+ OpenCode"]
        W2["Worker 2<br/>+ OpenCode"]
        WN["Worker N<br/>+ OpenCode"]
    end

    subgraph "External / Optional"
        DB[("PostgreSQL<br/>optional persistence")]
        S3[("S3/MinIO<br/>optional artifacts/state")]
        Auth["Keycloak / OIDC<br/>optional auth"]
        SQLite[("SQLite (local)<br/>OpenCode session cache")]
    end

    Web --> DOCS
    CLI --> APIHOST
    Agents --> APIHOST

    MKT --> Marketing
    DOCS --> DocsSite
    APIHOST --> API
    APIHOST --> MCP

    API --> A2A
    API --> Monitor
    API --> OpenCode

    API --> Redis
    Redis --> API
    API --> DB
    DB --> API
    API --> S3
    S3 --> API
    API -. optional .-> Auth
    OpenCode --> SQLite

    W1 -->|poll /v1/opencode/tasks| API
    W2 -->|poll /v1/opencode/tasks| API
    WN -->|poll /v1/opencode/tasks| API
    W1 -->|PUT status / POST output| API
    W2 -->|PUT status / POST output| API
    WN -->|PUT status / POST output| API
```

## Components

### FastAPI Server (Port 8000)

The main HTTP server handling:

- **A2A Protocol** (`POST /v1/a2a`, alias: `POST /`) - JSON-RPC 2.0 agent communication
- **REST APIs** (`/v1/monitor/*`, `/v1/opencode/*`) - Management and monitoring
- **Agent Card** (`/.well-known/agent-card.json`) - A2A discovery
- **Health Check** (`/health`) - Liveness/readiness probes

### MCP Server (Port 9000)

Model Context Protocol server for tool integration:

- Expose CodeTether capabilities as MCP tools
- Allow external agents to use CodeTether tools
- Bridge between A2A and MCP protocols

In Kubernetes deployments, the MCP server is typically exposed through the same
host as the API using a path prefix (e.g. `https://api.<domain>/mcp/v1/rpc`).

### Message Broker (Redis)

Handles distributed communication and coordination:

- **Task state** - Persist and coordinate tasks across replicas
- **Pub/Sub** - Agent discovery and inter-agent messaging
- **Shared state** - Optional durability and cross-replica rehydration

Note: workers do **not** consume tasks directly from Redis. Workers currently
poll the server over HTTP for pending tasks and report status/output back to
the server.

### OpenCode Bridge

Integrates AI coding agents:

- Register and manage codebases
- Trigger and control OpenCode agents
- Stream real-time agent output
- Manage session history

### Monitor API

Observability and management:

- Agent status and health
- Message history
- Real-time SSE streams
- Statistics and metrics

## Data Flow

### Task Execution Flow

```mermaid
sequenceDiagram
    participant C as Client
    participant S as CodeTether Server
    participant R as Redis
    participant W as Worker
    participant O as OpenCode

    C->>S: POST /v1/opencode/codebases/{codebase_id}/tasks
    S->>R: Persist task (pending)

    W->>S: GET /v1/opencode/tasks?status=pending
    S->>R: Read pending tasks
    S-->>W: Return next task

    W->>S: PUT /v1/opencode/tasks/{task_id}/status (running)
    W->>O: Execute (OpenCode / echo / noop)

    loop streaming output
        W->>S: POST /v1/opencode/tasks/{task_id}/output
        S-->>C: SSE event (/v1/opencode/codebases/{codebase_id}/events)
    end

    W->>S: PUT /v1/opencode/tasks/{task_id}/status (completed + result)
    S-->>C: SSE event: complete
```

### Real-time Streaming Flow

```mermaid
sequenceDiagram
    participant C as Client
    participant S as Server
    participant W as Worker
    participant O as OpenCode

    C->>S: GET /v1/opencode/codebases/{id}/events
    Note over C,S: SSE Connection Established

    W->>O: Run agent
    O->>W: Output/tool updates
    W->>S: POST /v1/opencode/tasks/{task_id}/output
    S->>C: event: output
    W->>S: PUT /v1/opencode/tasks/{task_id}/status
    S->>C: event: complete

    Note over W,S: In single-instance mode, the worker may be co-located with the server.
```

## Deployment Models

### Single Instance

Simplest deployment - everything in one process:

```
┌─────────────────────────────┐
│     CodeTether Server        │
│  ┌─────────┐ ┌───────────┐  │
│  │ API     │ │ OpenCode  │  │
│  │ Server  │ │ Bridge    │  │
│  └─────────┘ └───────────┘  │
│  ┌─────────┐ ┌───────────┐  │
│  │ MCP     │ │ SQLite    │  │
│  │ Server  │ │ DB        │  │
│  └─────────┘ └───────────┘  │
└─────────────────────────────┘
```

### Distributed with Workers

Scale horizontally with dedicated workers:

```
┌─────────────────┐     ┌─────────────────┐
│ CodeTether API   │     │ CodeTether API   │
│ (Instance 1)    │     │ (Instance 2)    │
└────────┬────────┘     └────────┬────────┘
         │                       │
         └───────────┬───────────┘
                     │
              ┌──────┴──────┐
              │   Redis     │
              │   Cluster   │
              └──────┬──────┘
                     │
    ┌────────────────┼────────────────┐
    │                │                │
┌───┴───┐       ┌────┴────┐      ┌────┴────┐
│Worker │       │ Worker  │      │ Worker  │
│   1   │       │    2    │      │    N    │
└───────┘       └─────────┘      └─────────┘
```

### Kubernetes

Full production deployment:

```
┌─────────────────────────────────────────────────┐
│                  Kubernetes                      │
│  ┌─────────────────────────────────────────┐    │
│  │              Ingress                     │    │
│  │   codetether.run → Marketing             │    │
│  │   docs.codetether.run → Docs             │    │
│  │   api.codetether.run → API (8000)        │    │
│  │   api.codetether.run/mcp → MCP (9000)    │    │
│  └─────────────────────────────────────────┘    │
│                                                  │
│  ┌──────────────────────────────┐              │
│  │ API Deploy (blue/green)      │              │
│  │ - codetether-a2a-server-blue │              │
│  │ - codetether-a2a-server-green│              │
│  └──────────────────────────────┘              │
│                                                  │
│  ┌──────────────┐  ┌──────────────┐            │
│  │ Marketing     │  │ Docs         │            │
│  │ (Deployment)  │  │ (Deployment) │            │
│  └──────────────┘  └──────────────┘            │
│                                                  │
│  ┌──────────────┐                              │
│  │    Redis     │                              │
│  │ (Deployment) │                              │
│  └──────────────┘                              │
│                                                  │
│  External (optional): PostgreSQL, S3/MinIO, Keycloak│
└─────────────────────────────────────────────────┘
```

## Security Model

### Authentication Layers

1. **Ingress** - TLS termination, rate limiting
2. **API Gateway** - Token validation, OIDC
3. **Service** - Role-based access control
4. **Data** - Encryption at rest

### Network Security

- Internal services communicate via ClusterIP
- External access only through Ingress
- Redis protected by NetworkPolicy
- Secrets managed via Kubernetes Secrets or Vault

## Next Steps

- [Installation](../getting-started/installation.md)
- [Kubernetes Deployment](../deployment/kubernetes.md)
- [Distributed Workers](../features/distributed-workers.md)
