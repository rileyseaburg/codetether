---
title: Architecture
description: AgentMesh Server architecture overview
---

# Architecture

AgentMesh Server is designed as a modular, scalable system for running AI agents in production.

## High-Level Architecture

```mermaid
graph TB
    subgraph Clients
        Web[Web Dashboard]
        CLI[CLI / SDK]
        Agents[External Agents]
    end

    subgraph "AgentMesh Server"
        API[FastAPI Server<br/>Port 8000]
        A2A[A2A Protocol<br/>Handler]
        Monitor[Monitor API]
        OpenCode[OpenCode Bridge]
        MCP[MCP Server<br/>Port 9000]
    end

    subgraph Infrastructure
        Redis[(Redis<br/>Message Broker)]
        DB[(SQLite/Postgres<br/>Persistence)]
        Auth[Keycloak<br/>Authentication]
    end

    subgraph Workers
        W1[Worker 1<br/>+ OpenCode]
        W2[Worker 2<br/>+ OpenCode]
        W3[Worker N<br/>+ OpenCode]
    end

    Web --> API
    CLI --> API
    Agents --> A2A

    API --> A2A
    API --> Monitor
    API --> OpenCode
    API --> MCP

    A2A --> Redis
    Monitor --> DB
    OpenCode --> DB
    API --> Auth

    Redis --> W1
    Redis --> W2
    Redis --> W3
```

## Components

### FastAPI Server (Port 8000)

The main HTTP server handling:

- **A2A Protocol** (`/v1/a2a`) - JSON-RPC 2.0 agent communication
- **REST APIs** (`/v1/monitor/*`, `/v1/opencode/*`) - Management and monitoring
- **Agent Card** (`/.well-known/agent-card.json`) - A2A discovery
- **Health Check** (`/health`) - Liveness/readiness probes

### MCP Server (Port 9000)

Model Context Protocol server for tool integration:

- Expose AgentMesh capabilities as MCP tools
- Allow external agents to use AgentMesh tools
- Bridge between A2A and MCP protocols

### Message Broker (Redis)

Handles distributed communication:

- **Task Queue** - Distribute tasks to workers
- **Pub/Sub** - Real-time event distribution
- **Session State** - Shared state across instances

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
    participant S as AgentMesh Server
    participant R as Redis
    participant W as Worker
    participant O as OpenCode

    C->>S: POST /v1/a2a (tasks/send)
    S->>R: Publish task
    R->>W: Task notification
    W->>O: Start agent
    O->>W: Stream output
    W->>R: Publish updates
    R->>S: Update notification
    S->>C: SSE events
    O->>W: Complete
    W->>R: Task complete
    R->>S: Complete notification
    S->>C: Final result
```

### Real-time Streaming Flow

```mermaid
sequenceDiagram
    participant C as Client
    participant S as Server
    participant O as OpenCode

    C->>S: GET /v1/opencode/codebases/{id}/events
    Note over C,S: SSE Connection Established
    O->>S: Output chunk
    S->>C: event: output
    O->>S: Tool use
    S->>C: event: tool_use
    O->>S: File change
    S->>C: event: file_change
    O->>S: Complete
    S->>C: event: complete
```

## Deployment Models

### Single Instance

Simplest deployment - everything in one process:

```
┌─────────────────────────────┐
│     AgentMesh Server        │
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
│ AgentMesh API   │     │ AgentMesh API   │
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
│  │   agentmesh.run → API Service           │    │
│  └─────────────────────────────────────────┘    │
│                                                  │
│  ┌──────────────┐  ┌──────────────┐            │
│  │ API Pod 1    │  │ API Pod 2    │ ← HPA      │
│  │ (Deployment) │  │ (Deployment) │            │
│  └──────────────┘  └──────────────┘            │
│                                                  │
│  ┌──────────────┐  ┌──────────────┐            │
│  │ Worker Pod 1 │  │ Worker Pod 2 │ ← HPA      │
│  │ (StatefulSet)│  │ (StatefulSet)│            │
│  └──────────────┘  └──────────────┘            │
│                                                  │
│  ┌──────────────┐  ┌──────────────┐            │
│  │    Redis     │  │   Postgres   │            │
│  │ (StatefulSet)│  │ (StatefulSet)│            │
│  └──────────────┘  └──────────────┘            │
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
- [Distributed Workers](distributed-workers.md)
