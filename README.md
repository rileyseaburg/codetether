<div align="center">

# 🔗 CodeTether

### **The control plane for production AI agents**

[![PyPI version](https://img.shields.io/pypi/v/codetether.svg)](https://pypi.org/project/codetether/)
[![PyPI downloads](https://img.shields.io/pypi/dm/codetether.svg)](https://pypi.org/project/codetether/)
[![A2A Protocol](https://img.shields.io/badge/A2A_Protocol-v0.3-green.svg)](https://a2a-protocol.org)
[![Production Ready](https://img.shields.io/badge/status-production--ready-brightgreen.svg)](https://api.codetether.run)
[![Apache License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED.svg)](https://www.docker.com/)
[![Kubernetes](https://img.shields.io/badge/kubernetes-ready-326CE5.svg)](https://kubernetes.io/)

**Run autonomous coding, operations, and workflow agents with real routing, policy, workers, observability, and auditability.**

[🚀 Quick Start](#-quick-start) • [🏗️ Architecture](#️-architecture) • [🔐 Security](#-security-and-provenance) • [📖 Documentation](https://docs.codetether.run)

---

</div>

## 🎯 What is CodeTether?

CodeTether is an open-source **agent operations platform**: a server, worker runtime, policy layer, dashboard, and MCP/A2A integration stack for turning one-off AI agent scripts into governed production systems.

Most agent demos stop at "the model called a tool." CodeTether focuses on everything around that call:

- **Where does the work run?** Distributed workers claim tasks over SSE and execute close to the relevant codebase.
- **Who is allowed to do what?** Keycloak, RBAC, tenant isolation, OPA policies, and provenance checks gate API and agent actions.
- **How do agents coordinate?** A2A endpoints, task queues, worker routing, MCP tools, and Ralph PRD execution provide orchestration primitives.
- **How do humans stay in control?** Dashboard streaming, email reply continuation, audit logs, and explicit task lifecycle state keep work observable.
- **How does it scale?** PostgreSQL persistence, Redis messaging, Helm charts, worker registration, and codebase-aware routing support multi-tenant deployments.

```text
┌────────────────────────────── CodeTether ──────────────────────────────┐
│                                                                         │
│  Humans / Apps / A2A Clients / MCP Clients                              │
│                  │                                                      │
│                  ▼                                                      │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ A2A + REST API Server                                             │  │
│  │ tasks • agents • workers • codebases • sessions • OKRs            │  │
│  └───────────────┬───────────────────────────────┬───────────────────┘  │
│                  │                               │                      │
│                  ▼                               ▼                      │
│  ┌─────────────────────────────┐   ┌─────────────────────────────────┐  │
│  │ Policy + Provenance          │   │ Durable State + Routing          │  │
│  │ Keycloak • RBAC • OPA • APF  │   │ PostgreSQL • Redis • SSE         │  │
│  └─────────────────────────────┘   └───────────────┬─────────────────┘  │
│                                                     │                    │
│                                                     ▼                    │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ Distributed Workers                                               │  │
│  │ Rust/Python agents • MCP tools • codebase routing • model routing │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 🧭 When to use CodeTether

Use CodeTether when you need to run agents as part of a real system, not just a notebook or chatbot:

| Need | CodeTether gives you |
| --- | --- |
| Autonomous development | Ralph executes PRDs end-to-end: stories → code → tests → commits. |
| Agent tool access | MCP server/tools for files, tasks, PRDs, worker control, and integrations. |
| Distributed execution | Workers register capabilities/codebases and claim tasks from the server. |
| Multi-tenant production auth | Keycloak SSO, RBAC, OPA route policies, and PostgreSQL RLS. |
| Agent action accountability | Agent Provenance Framework tracks origin, inputs, delegation, runtime, and output. |
| Human-in-the-loop operations | Dashboard streaming, task lifecycle state, notifications, and email replies. |
| Kubernetes deployment | Helm charts, Redis/PostgreSQL integration, health checks, and horizontal scaling. |

## ✨ Why CodeTether?

<table>
<tr>
<td width="50%">

### 🤖 **Ralph: Autonomous Development**

Ralph implements entire PRDs with zero human intervention. Define user stories, Ralph writes the code, runs tests, and commits—autonomously iterating until all acceptance criteria pass.

### 🛠️ **MCP Tool Integration**

**29 MCP tools** including Ralph integration. AI assistants can autonomously create PRDs, start Ralph runs, and monitor execution—all via MCP. File systems, databases, APIs, and more.

### 💻 **AI Coding at Scale**

Deploy AI coding agents across your infrastructure using the CodeTether worker runtime. Automated code generation, refactoring, and testing with codebase-aware routing.

### 🔄 **RLM (Recursive Language Models)**

Process arbitrarily long contexts through recursive LLM calls in a Python REPL. Analyze entire monorepos without context limits using programmatic sub-LLM queries.

### 📧 **Email Reply to Continue Tasks**

Workers send email notifications when tasks complete. **Reply directly to the email** to continue the conversation—the agent picks up right where it left off. No dashboard needed.

### ⚡ **Zapier Integration**

Connect CodeTether to 6,000+ apps with our native Zapier integration. 18 components: 3 triggers, 9 actions, 7 searches covering tasks, agents, codebases, cron jobs, billing, and PRD generation—no code required.

 </td>
<td width="50%">

### 🎤 **Voice Agent**

Real-time voice interactions with AI agents through LiveKit integration. Multi-model support and session playback.

### 📡 **Real-Time Streaming**

Watch agents think in real-time. SSE streaming for instant feedback and human intervention.

### 🚀 **Production Ready**

Connect workers to `https://api.codetether.run` for live task execution. Helm charts and horizontal scaling included.

### 🔐 **Governed Agent Actions**

Keycloak SSO, RBAC, OPA policy enforcement, PostgreSQL RLS, audit logs, and Agent Provenance Framework checks for origin, taint, delegation, runtime, and output claims.

### ☸️ **Deploy Anywhere**

Helm charts, horizontal scaling, blue-green deployments. Production from day one on any cloud or on-premise infrastructure.

</td>
</tr>
</table>

## 🔗 A2A Protocol Compliance

CodeTether implements the **A2A Protocol v0.3** specification using the official `a2a-sdk` from Google, ensuring full interoperability with any A2A-compliant client or agent.

### Standard Endpoints

| Endpoint                       | Description                                         |
| ------------------------------ | --------------------------------------------------- |
| `/.well-known/agent-card.json` | Agent capability discovery and metadata             |
| `/a2a/jsonrpc`                 | JSON-RPC 2.0 endpoint for A2A protocol messages     |
| `/a2a/rest/*`                  | RESTful API endpoints for task and agent management |

### Interoperability

- **Any A2A Client**: Connect using standard A2A protocol clients from any language or platform
- **Agent Discovery**: Automatic capability discovery via well-known endpoint
- **Cross-Platform**: Seamlessly communicate with other A2A-compliant agents
- **SDK Support**: Built on Google's official `a2a-sdk` for guaranteed compatibility

```bash
# Discover agent capabilities
curl https://api.codetether.run/.well-known/agent-card.json

# Send A2A message via JSON-RPC
curl -X POST https://api.codetether.run/a2a/jsonrpc \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "message/send", "params": {...}, "id": 1}'
```

## 🚀 Quick Start

### Install from PyPI

```bash
pip install codetether
```

### Or Install from Source

```bash
git clone https://github.com/rileyseaburg/codetether.git
cd A2A-Server-MCP && pip install -e .

# For production (PostgreSQL persistence):
export DATABASE_URL=postgresql://user:password@host:5432/a2a_server

# Start the server (defaults to `run`)
codetether --port 8000
```

### Docker

```bash
docker run -p 8000:8000 registry.quantum-forge.net/library/a2a-server-mcp:latest
```

### CodeTether AI CLI

Download pre-built binaries from [GitHub Releases](https://github.com/rileyseaburg/A2A-Server-MCP/releases):

**One-line install (Linux/macOS):**
```bash
curl -fsSL https://raw.githubusercontent.com/rileyseaburg/A2A-Server-MCP/main/scripts/install-agent.sh | bash
```

**One-line install (Windows PowerShell):**
```powershell
Invoke-Expression (Invoke-WebRequest -Uri "https://raw.githubusercontent.com/rileyseaburg/A2A-Server-MCP/main/scripts/install-agent.ps1" -UseBasicParsing).Content
```

**Or download manually:**
- Linux: `agent-v1.1.25-linux-x64.tar.gz`
- macOS: `agent-v1.1.25-darwin-arm64.tar.gz`
- Windows: `agent-v1.1.25-windows-x64.zip`

**Available platforms:** Linux (x64/ARM64/glibc/musl), macOS (x64/ARM64), Windows (x64) - with baseline builds for older CPUs.

### Kubernetes (Production)

```bash
helm install codetether oci://registry.quantum-forge.net/library/a2a-server \
  --namespace codetether --create-namespace
```

### Distributed Workers (Scale Anywhere)

Run agents on any machine with the CodeTether Worker (Rust binary):

```bash
git clone https://github.com/rileyseaburg/codetether.git
cd codetether

# One-command deploy (foreground, registers to this repo as a codebase)
./deploy-worker.sh --codebases /path/to/your/project

# Or install as a persistent systemd service
sudo ./deploy-worker.sh --systemd --codebases /path/to/your/project
```

Or run the binary directly:

```bash
codetether worker --server https://api.codetether.run --codebases /path/to/project --auto-approve safe
```

Learn more in the [Distributed Workers Guide](https://docs.codetether.run/features/distributed-workers/).

### 🚀 Production Worker Setup

To connect a local worker to the production CodeTether service:

1. **Quick deploy** (recommended):
    ```bash
    # Foreground (dev/testing)
    ./deploy-worker.sh --server https://api.codetether.run --codebases /path/to/project

    # Systemd service (production)
    sudo ./deploy-worker.sh --systemd --server https://api.codetether.run --codebases /path/to/project
    ```

2. **Or install manually**:
    ```bash
    sudo ./legacy/agent_worker/install-codetether-worker.sh --codebases /path/to/project
    ```

    Build from source:
    ```bash
    sudo ./legacy/agent_worker/install-codetether-worker.sh --from-cargo --codebases /path/to/project
    ```

3. **Configure** (if using systemd):
   Edit `/etc/codetether-worker/env`:

    ```bash
    A2A_SERVER_URL=https://api.codetether.run
    A2A_CODEBASES=/path/to/project-a,/path/to/project-b
    A2A_AUTO_APPROVE=safe   # all, safe (read-only), or none
    ANTHROPIC_API_KEY=sk-ant-...   # or OPENAI_API_KEY, GOOGLE_GENERATIVE_AI_API_KEY
    ```

4. **Start the service**:
    ```bash
    sudo systemctl start codetether-worker
    ```
    ```bash
    # Or use the makefile shortcut:
    make local-worker-restart
    ```

**How it works:**

- Worker connects to the A2A server via SSE (Server-Sent Events)
- Registers itself with `--codebases` paths — the server routes tasks by codebase ownership
- Server pushes task assignments to the worker in real-time
- Worker executes tasks using its built-in agentic loop (28+ tools, 8 LLM providers)
- Worker streams results back to the server
- Use `make local-worker-restart` to restart the worker service

**That's it.** Your agent platform is running at `http://localhost:8000`

## 🎬 See It In Action

### Talk to Your Agents

```bash
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "message/send",
    "params": {"message": {"parts": [{"type": "text", "content": "Calculate 25 * 4"}]}}
  }'
```

### Deploy AI Coding Agents

```bash
# Register a codebase
curl -X POST http://localhost:8000/v1/agent/codebases \
  -H "Content-Type: application/json" \
  -d '{"name": "my-app", "path": "/home/user/my-app"}'

# Trigger an agent task
curl -X POST http://localhost:8000/v1/agent/codebases/{id}/trigger \
  -d '{"prompt": "Add unit tests for the auth module", "agent": "build"}'
```

### Stream Real-Time Output

```bash
curl http://localhost:8000/v1/agent/codebases/{id}/events
```

### 📧 Email Reply to Continue Tasks

When a task completes, workers send you an email. **Just reply to continue the conversation**—no dashboard, no CLI, just email.

```
From: noreply@codetether.run
To: you@example.com
Subject: [A2A] Task completed: Add unit tests
Reply-To: task+sess_abc123@inbound.codetether.run

✓ COMPLETED

Your task "Add unit tests" finished successfully.
Reply to this email to continue the conversation.

---
You: "Great, now add integration tests too"
→ Agent picks up and continues working
```

**How it works:**

1. Worker completes task → sends email with special `reply-to` address
2. You reply to the email with follow-up instructions
3. SendGrid forwards your reply to CodeTether
4. Server creates a continuation task with your message
5. Worker resumes the same session and keeps working

**Zero friction.** Check your email, reply, done.

## 🏗️ Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              CodeTether Platform                             │
│                                                                              │
│  ┌─────────────────────┐       ┌──────────────────────────────────────────┐  │
│  │   Dashboard (Next.js)│       │         A2A Protocol Server              │  │
│  │   port 3001 (HTTPS)  │──────▶│         (Python / FastAPI)               │  │
│  │                      │ proxy │                                          │  │
│  │  • Trigger agents    │/api/v1│  ┌─────────┐ ┌───────────┐ ┌─────────┐  │  │
│  │  • Monitor swarms    │       │  │ A2A RPC │ │ REST API  │ │ SSE     │  │  │
│  │  • Manage codebases  │       │  │ /a2a/*  │ │ /v1/*     │ │ Push    │  │  │
│  │  • View sessions     │       │  └────┬────┘ └─────┬─────┘ └────┬────┘  │  │
│  └─────────────────────┘       │       │             │             │       │  │
│                                 │       ▼             ▼             ▼       │  │
│  ┌─────────────────────┐       │  ┌──────────────────────────────────────┐ │  │
│  │   Keycloak SSO       │◀─────│  │         Auth & Authorization         │ │  │
│  │   (Identity Provider)│       │  │  Keycloak JWT → OPA Policies → RLS  │ │  │
│  └─────────────────────┘       │  └──────────────────────────────────────┘ │  │
│                                 │                    │                      │  │
│                                 │       ┌────────────┼────────────┐        │  │
│                                 │       ▼            ▼            ▼        │  │
│                                 │  ┌─────────┐ ┌──────────┐ ┌──────────┐  │  │
│                                 │  │Orchestr.│ │ Worker   │ │ Task     │  │  │
│                                 │  │& Routing│ │ Registry │ │ Queue    │  │  │
│                                 │  └────┬────┘ └────┬─────┘ └────┬─────┘  │  │
│                                 │       │           │             │        │  │
│                                 └───────┼───────────┼─────────────┼────────┘  │
│                                         │           │             │           │
│  ┌──────────────────┐                   │           │             │           │
│  │   Redis           │◀─────────────────┘           │             │           │
│  │   (Session Sync)  │                              │             │           │
│  └──────────────────┘                               │             │           │
│                                                     │             │           │
│  ┌──────────────────┐                               │             │           │
│  │   PostgreSQL      │◀─────────────────────────────┘             │           │
│  │   (RLS Isolation) │  workers, codebases, tasks,                │           │
│  │                    │  sessions, tenants, OKRs                   │           │
│  └──────────────────┘                                             │           │
│                                                                    │           │
│         ┌──────────────────────────────────────────────────────────┘           │
│         │  SSE stream (tasks/stream)                                          │
│         ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────┐  │
│  │                        Distributed Workers                              │  │
│  │                                                                         │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │  │
│  │  │  Worker A     │  │  Worker B     │  │  Worker C     │   ...          │  │
│  │  │  (Rust)       │  │  (Rust)       │  │  (Python)     │                │  │
│  │  │              │  │              │  │              │                │  │
│  │  │  codebases:  │  │  codebases:  │  │  codebases:  │                │  │
│  │  │  /app-1      │  │  /app-2      │  │  /app-3      │                │  │
│  │  │  /app-4      │  │  global      │  │              │                │  │
│  │  │              │  │              │  │              │                │  │
│  │  │  28+ tools   │  │  28+ tools   │  │  MCP tools   │                │  │
│  │  │  8 LLM provs │  │  8 LLM provs │  │              │                │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘                  │  │
│  └─────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Core Components

| Component | Purpose | Technology |
|-----------|---------|------------|
| **A2A Protocol Server** | Agent communication, orchestration, task routing | Python, FastAPI, Redis |
| **Distributed Workers** | Scale agent execution across machines | Rust binary (`codetether worker`), Systemd/K8s |
| **MCP Integration** | Tool access & resource management (29 tools) | Model Context Protocol |
| **PostgreSQL Database** | Durable storage with Row-Level Security tenant isolation | PostgreSQL, asyncpg, RLS policies |
| **Dashboard / Monitor UI** | Real-time agent monitoring, task triggering | Next.js, React, SSE streaming |
| **RLM Engine** | Recursive context processing for large codebases | Python REPL, sub-LLM calls |
| **OPA Policy Engine** | Fine-grained API authorization (160+ route rules) | Open Policy Agent, Rego |
| **Agent Provenance Framework** | Verifiable causal history for autonomous agent actions | Python verifier, OPA/Rego policies |
| **Keycloak SSO** | Identity management, JWT tokens, multi-tenant auth | Keycloak, NextAuth |

### Task Lifecycle

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  submitted   │────▶│   routed     │────▶│   claimed    │────▶│   running    │────▶│  completed   │
│              │     │              │     │              │     │              │     │  / failed    │
│ User creates │     │ Orchestrator │     │ Worker picks │     │ Agent loop   │     │ Result sent  │
│ task via API │     │ selects best │     │ up from SSE  │     │ with 28+     │     │ back to      │
│ or dashboard │     │ worker match │     │ task stream   │     │ tools, LLMs  │     │ server + DB  │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                     ▲                                                              │
                     │  model tier routing                                          │  email notify
                     │  codebase matching                                           │  SSE broadcast
                     │  worker capability check                                    ▼
```

### How Workers Connect

1. **Register** — Worker sends `POST /v1/agent/workers/register` with its `worker_id`, hostname, supported models, and list of codebase paths it can access
2. **Connect** — Worker opens SSE stream at `GET /v1/worker/tasks/stream` to receive task assignments in real-time
3. **Heartbeat** — Periodic `POST /v1/agent/workers/{id}/heartbeat` keeps the worker alive in the registry
4. **Claim** — When a task arrives, worker calls `POST /v1/worker/tasks/{id}/claim` (atomic, prevents double-assignment)
5. **Execute** — Worker runs its agentic loop (file I/O, git, shell, code search, etc.) with the selected LLM
6. **Complete** — Worker posts results back via `POST /v1/agent/tasks/{id}/complete`, status updates stream to dashboard via SSE

### Workspace / Codebase Routing

Workers register the **codebases** (filesystem paths) they can access. When a task targets a specific codebase, the server routes it only to workers that have registered that path:

```
Task: "Add tests for auth" → codebase: /home/user/my-app
  └─▶ Server checks WorkerRegistry
       ├─ Worker A: [/home/user/my-app, /home/user/api] ← MATCH ✓
       ├─ Worker B: [/home/user/frontend]               ← skip
       └─ Worker C: [global]                            ← MATCH ✓ (global catches all)
```

Workers with `global` codebase registration can handle any task regardless of path.

### Security and Provenance

```
Request → Keycloak JWT validation
       → OPA policy check (160+ route rules, RBAC)
       → Agent Provenance Framework check (origin, inputs, delegation, runtime, output)
       → PostgreSQL RLS (tenant_id enforced per-row)
       → Response (only tenant's own data)
```

CodeTether now includes an **Agent Provenance Framework (APF)** policy layer for autonomous multi-agent systems. When provenance claims are present, APF validates five dimensions of causal history before sensitive actions are authorized:

- **Origin** — locks action requests to the original session intent hash.
- **Inputs** — propagates taint markers and detects taint stripping.
- **Delegation** — enforces capability attenuation for operations, budgets, and spawn limits.
- **Runtime** — records runtime and attestation metadata for the executing agent.
- **Output** — records output-context and tool-call attestations.

APF is implemented in both Python (`a2a_server/provenance.py`) and OPA/Rego (`policies/provenance.rego`) so local policy checks and deployed OPA sidecars enforce the same rules. See the RFC draft at [`rfc/Agent-Provenance-Framework_for_Autonomous-Multi-Agent-Systems.txt`](rfc/Agent-Provenance-Framework_for_Autonomous-Multi-Agent-Systems.txt).

### Platform Components

```
codetether/
├── 🌐 a2a_server/         # A2A protocol + REST APIs (FastAPI)
├── 🖥️ marketing-site/     # Dashboard + marketing (Next.js)
├── 👷 codetether-agent/    # Rust worker binary (28+ tools, 8 LLM providers)
├── 📚 codetether-docs/     # MkDocs Material documentation site
├── 📋 policies/            # OPA Rego authorization + provenance policies
├── 🧾 rfc/                 # Agent Provenance Framework RFC draft
├── ⎈ chart/               # Unified Helm chart (server + UI + docs)
└── 🔌 integrations/       # Zapier, n8n, external connectors
```

### Data Flow

```
Dashboard ──proxy──▶ A2A Server ──SSE push──▶ Worker (claims task, runs agent)
    ▲                    │   ▲                     │
    │                    │   │                     │
    │                    ▼   │ heartbeat            │ POST results
    │               PostgreSQL ◀───────────────────┘
    │               (tasks, sessions, workers, codebases)
    │                    │
    └────────────────────┘
         reads tasks, sessions, routing snapshots
```

Workers sync sessions from local storage to PostgreSQL. The dashboard and API read from PostgreSQL, providing a consistent view across server replicas and restarts.

## 📦 What's Included

### Core Platform

- ✅ Full A2A Protocol implementation
- ✅ MCP tool integration
- ✅ Redis message broker
- ✅ PostgreSQL durable storage (sessions, workspaces, tasks, OKRs)
- ✅ SSE real-time streaming
- ✅ Worker sync to PostgreSQL from CodeTether storage

### Enterprise Features

- ✅ Keycloak SSO integration
- ✅ Role-based access control (RBAC)
- ✅ PostgreSQL Row-Level Security (RLS) for database-level tenant isolation
- ✅ OPA policy engine for API-level authorization
- ✅ Audit logging
- ✅ Agent Provenance Framework for origin, taint, delegation, runtime, and output checks
- ✅ Network policies

### DevOps Ready

- ✅ Unified Helm chart (server + marketing + docs)
- ✅ Blue-green deployments
- ✅ Horizontal pod autoscaling
- ✅ Health checks & metrics

### Developer Experience

- ✅ Real-time Monitor UI
- ✅ Swift iOS/macOS app
- ✅ CLI tools
- ✅ Comprehensive API docs
- ✅ Voice agent with LiveKit
- ✅ Marketing coordinator for task orchestration
- ✅ Worker SSE push notifications
- ✅ 27 marketing MCP tools (creative, campaigns, analytics)
- ✅ **Email reply continuation** - reply to task emails to keep working

## 🛠️ Deployment Options

| Environment    | Command                              | Description                 |
| -------------- | ------------------------------------ | --------------------------- |
| **Local**      | `python run_server.py` or `make run` | Development mode            |
| **Production** | `DATABASE_URL=... make k8s-prod`     | Full PostgreSQL persistence |
| **Docker**     | `docker-compose up`                  | Single container            |
| **Kubernetes** | `make k8s-prod`                      | Full production stack       |

### Codex MCP (Local)

Codex CLI should use CodeTether over stdio via `~/.codex/config.toml` for local workspaces.

```toml
[mcp_servers.codetether]
command = "/absolute/path/to/codetether"
args = ["mcp", "serve", "/absolute/workspace/path"]
```

### Production Deployment

```bash
# Build and deploy everything
make k8s-prod

# This builds & deploys:
# ✅ API Server (api.codetether.run)
# ✅ Marketing Site (codetether.run)
# ✅ Documentation (docs.codetether.run)
# ✅ Redis cluster
```

## 🔧 Environment Variables

| Variable          | Description                                                     | Default                               | Required         |
| ----------------- | --------------------------------------------------------------- | ------------------------------------- | ---------------- |
| `DATABASE_URL`    | PostgreSQL connection string                                    | `postgresql://user:pass@host:5432/db` | Yes (production) |
| `A2A_REDIS_URL`   | Redis URL for message broker                                    | `redis://localhost:6379`              | No               |
| `A2A_AUTH_TOKENS` | Comma-separated auth tokens (format: `name:token,name2:token2`) | `""`                                  | No               |
| `OPENCODE_HOST`   | Host where CodeTether API is running (container→host)             | `localhost`                           | No               |
| `OPENCODE_PORT`   | Default CodeTether server port                                    | `9777`                                | No               |
| `A2A_SERVER_URL`  | Production server URL (for workers)                             | `http://localhost:8000`               | No               |

**Setting DATABASE_URL:**

```bash
# Local development (with PostgreSQL):
export DATABASE_URL=postgresql://a2a:a2a_password@localhost:5432/a2a_server

# Production:
export DATABASE_URL=postgresql://user:password@prod-db:5432/a2a_server
```

## 🐛 Troubleshooting

### Sessions Not Appearing in UI?

If you don't see sessions in the production API for a codebase (like "spotlessbinco"):

1. **Check worker is running:**

    ```bash
    sudo systemctl status a2a-agent-worker
    ```

2. **Check worker logs for sync errors:**

    ```bash
    sudo journalctl -fu a2a-agent-worker | grep -i "session\|sync"
    ```

3. **Verify sessions are in PostgreSQL:**

    ```bash
    # Via API:
    curl http://localhost:8000/v1/agent/database/sessions

    # Or via psql:
    psql -d a2a_server -c "SELECT id, codebase_id, title FROM sessions ORDER BY updated_at DESC LIMIT 10;"
    ```

4. **Restart worker to force re-sync:**
    ```bash
    make local-worker-restart
    ```

**How it works:**

- Workers read local CodeTether storage from `~/.local/share/agent/`
- Workers POST sessions to `/v1/agent/codebases/{id}/sessions/sync`
- Server persists to PostgreSQL via `db_upsert_session()`
- Monitor UI reads from PostgreSQL via `db_list_sessions()`
- No SQLite involved! All data goes through PostgreSQL

### Worker Not Connecting?

1. **Check `DATABASE_URL` in worker env:**

    ```bash
    cat /etc/a2a-worker/env
    # Should contain: DATABASE_URL=postgresql://...
    ```

2. **Check network connectivity:**

    ```bash
    curl -v https://api.codetether.run/v1/health
    ```

3. **Verify worker is registered:**
    ```bash
    curl http://localhost:8000/v1/agent/database/workers
    ```

For more troubleshooting, see [docs.codetether.run/troubleshooting](https://docs.codetether.run/troubleshooting/)

### Production Deployment

## 🔌 Integrations

<table>
<tr>
<td align="center"><strong>LLMs</strong></td>
<td align="center"><strong>Tools</strong></td>
<td align="center"><strong>Infrastructure</strong></td>
</tr>
<tr>
<td>

- Claude (Anthropic)
- GPT-4 (OpenAI)
- Gemini (Google)
- DeepSeek
- Grok (xAI)

</td>
<td>

- File systems
- Databases
- Git repositories
- REST APIs
- Custom MCP servers

</td>
<td>

- Kubernetes
- Docker
- Redis
- Keycloak
- Any cloud

</td>
</tr>
</table>

## 📚 Documentation

| Resource                     | Link                                                                                          |
| ---------------------------- | --------------------------------------------------------------------------------------------- |
| 📖 **Full Documentation**    | [docs.codetether.run](https://docs.codetether.run)                                            |
| 🚀 **Quick Start Guide**     | [Getting Started](https://docs.codetether.run/getting-started/quickstart/)                    |
| 🔧 **API Reference**         | [API Docs](https://docs.codetether.run/api/overview/)                                         |
| 🤖 **Ralph Guide**           | [Ralph Autonomous Development](https://docs.codetether.run/features/ralph/)                   |
| 👷 **Agent Worker Guide**    | [Agent Worker](https://docs.codetether.run/features/agent-worker/)                            |
| 🔄 **RLM Guide**             | [RLM (Recursive Language Models)](docs/agent-integration.md#rlm-recursive-language-models) |
| ⚡ **Zapier Integration**    | [Zapier](https://docs.codetether.run/features/zapier/)                                        |
| 🎤 **Voice Agent**           | [Voice Agent](https://docs.codetether.run/features/voice-agent/)                              |
| 📊 **Marketing Tools**       | [Marketing Tools](https://docs.codetether.run/features/marketing-tools/)                      |
| 🤖 **Marketing Coordinator** | [Marketing Coordinator](https://docs.codetether.run/features/marketing-coordinator/)          |
| 🔔 **Worker SSE**            | [Worker SSE](https://docs.codetether.run/features/worker-sse/)                                |
| ☸️ **Kubernetes Deployment** | [Helm Charts](https://docs.codetether.run/deployment/helm/)                                   |
| 🔐 **Authentication**        | [Keycloak Setup](https://docs.codetether.run/auth/keycloak/)                                  |

For detailed technical documentation, see [DEVELOPMENT.md](DEVELOPMENT.md).

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

```bash
# Setup development environment
git clone https://github.com/rileyseaburg/codetether.git
cd A2A-Server-MCP
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt -r requirements-test.txt

# Run tests
pytest tests/

# Start development server (Python + Next.js)
make dev
```

## 📄 License

Apache License 2.0 - See [LICENSE](LICENSE) for details.

---

<div align="center">

**Built with ❤️ by the CodeTether Team**

[Website](https://codetether.run) • [Documentation](https://docs.codetether.run) • [GitHub](https://github.com/rileyseaburg/codetether)

</div>
