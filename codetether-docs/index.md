---
title: CodeTether Server
description: Production-ready A2A Protocol implementation for AI agent coordination
---

# CodeTether Server

**Turn AI Agents Into Production Systems.**

!!! success "v1.4.1 Production Release"
    CodeTether is battle-tested and running in production at [api.codetether.run](https://api.codetether.run). Now with **MCP-to-Ralph E2E integration** - AI assistants can autonomously create and execute PRDs via 29 MCP tools.

CodeTether Server is a production-ready implementation of the [A2A (Agent-to-Agent) Protocol](https://a2a-protocol.org/), the open standard from the Linux Foundation that enables AI agents to communicate, collaborate, and solve complex problems together.

<div class="grid cards" markdown>

-   :material-rocket-launch:{ .lg .middle } __Get Started in 5 Minutes__

    ---

    Install CodeTether and run your first multi-agent workflow

    [:octicons-arrow-right-24: Quick Start](getting-started/quickstart.md)

-   :material-api:{ .lg .middle } __Full A2A Protocol Support__

    ---

    Complete implementation of the A2A specification with extensions

    [:octicons-arrow-right-24: A2A Protocol](concepts/a2a-protocol.md)

-   :material-kubernetes:{ .lg .middle } __Deploy Anywhere__

    ---

    Docker, Kubernetes, or bare metal with Helm charts included

    [:octicons-arrow-right-24: Deployment](deployment/docker.md)

-   :material-code-braces:{ .lg .middle } __OpenCode Integration__

    ---

    Bridge AI coding agents to your codebase with session management

    [:octicons-arrow-right-24: OpenCode](features/opencode.md)

</div>

---

## What is CodeTether?

CodeTether Server provides the infrastructure layer for running AI agents in production:

- **[Ralph Autonomous Development](features/ralph.md)** — Implement entire PRDs autonomously with zero human intervention
- **[RLM (Recursive Language Models)](features/opencode.md#rlm-recursive-language-models)** — Process arbitrarily large codebases without context limits
- **[Zapier Integration](features/zapier.md)** — Connect to 5,000+ apps with no-code automation
- **A2A Protocol Native** — Full implementation of the [A2A specification](https://a2a-protocol.org/specification.md) for agent-to-agent communication
- **[Distributed Workers](features/distributed-workers.md)** — Run agents across multiple machines with automatic task routing
- **Real-time Streaming** — SSE-based live output streaming for long-running agent tasks
- **Session Management** — Resume conversations, sync across devices, maintain context
- **Enterprise Security** — Keycloak OIDC, API tokens, audit logging
- **OpenCode Bridge** — Native integration with OpenCode AI coding agents
- **[Deploy Anywhere](deployment/docker.md)** — Run on Docker, Kubernetes, or bare metal with ease
- **[Email Reply Continuation](features/agent-worker.md#email-notifications)** — Reply to task notification emails to continue conversations with agents

## A2A Protocol Implementation

CodeTether implements the complete A2A Protocol specification:

| A2A Feature | CodeTether Support | Reference |
|-------------|-------------------|-----------|
| Agent Discovery | ✅ `/.well-known/agent-card.json` | [Spec §5](https://a2a-protocol.org/specification.md#5-agent-discovery-the-agent-card) |
| JSON-RPC 2.0 | ✅ Full support | [Spec §6](https://a2a-protocol.org/specification.md#6-protocol-data-objects) |
| Task Management | ✅ Create, cancel, status | [Spec §7](https://a2a-protocol.org/specification.md#7-json-rpc-methods) |
| Streaming (SSE) | ✅ Real-time artifacts | [Spec §8](https://a2a-protocol.org/specification.md#8-streaming-sse) |
| Push Notifications | ✅ Webhook callbacks | [Topics](https://a2a-protocol.org/topics/streaming-and-async.md) |
| Multi-turn Conversations | ✅ Session continuity | [Topics](https://a2a-protocol.org/topics/key-concepts.md) |

Plus CodeTether extensions:

- **[Ralph](features/ralph.md)** — Autonomous development loop that implements PRDs with self-healing retry
- **[RLM](features/opencode.md#rlm-recursive-language-models)** — Recursive Language Models for infinite context processing
- **[Zapier](features/zapier.md)** — Native OAuth2 integration with triggers, actions, and searches
- **Distributed task coordination** — Redis-backed task/state coordination (workers poll the server over HTTP)
- **OpenCode Integration** — AI coding agent bridge with codebase registration
- **Monitor UI** — Web dashboard for real-time agent observation
- **MCP Tools** — Model Context Protocol tool server
- **Email Reply to Continue** — Reply directly to task notification emails to keep working with an agent
- **Task Reaper** — Automatic stuck task recovery with retry and notification

## Quick Start

### Option 1: Docker (Server)

```bash
# Run the server
docker run -d -p 8000:8000 -p 9000:9000 \
  ghcr.io/rileyseaburg/codetether-server:latest
```

### Option 2: pip (Agent Worker)

The pip package is primarily for installing the **agent worker** on machines where your code lives:

```bash
# Install the worker
pip install codetether

# Configure and start (see installation docs for systemd setup)
codetether-worker --server-url https://api.codetether.run --codebases /path/to/code
```

### Send a Task

```bash
curl -X POST http://localhost:8000/v1/a2a \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "message/send",
    "params": {
      "message": {
        "parts": [{"type": "text", "content": "Analyze this codebase"}]
      }
    },
    "id": "1"
  }'
```

## Architecture Overview

At a high level:

- Clients talk to the API (`:8000`) for A2A JSON-RPC (`/v1/a2a`) and REST (`/v1/opencode/*`, `/v1/monitor/*`).
- Workers run OpenCode and poll the server for pending tasks over HTTP.
- Redis provides pub/sub plus shared task/state coordination.
- The MCP server (`:9000`) exposes CodeTether capabilities as MCP tools.

For diagrams and deeper detail, see [Architecture](concepts/architecture.md).

## Next Steps

<div class="grid cards" markdown>

-   :material-download:{ .lg .middle } __Installation__

    [:octicons-arrow-right-24: Install Guide](getting-started/installation.md)

-   :material-cog:{ .lg .middle } __Configuration__

    [:octicons-arrow-right-24: Config Reference](getting-started/configuration.md)

-   :material-api:{ .lg .middle } __API Reference__

    [:octicons-arrow-right-24: API Docs](api/overview.md)

-   :material-github:{ .lg .middle } __Source Code__

    [:octicons-arrow-right-24: GitHub](https://github.com/rileyseaburg/codetether)

</div>
