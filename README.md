<div align="center">

# 🔗 CodeTether

### **Turn AI Agents into Production Systems**

[![Apache License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED.svg)](https://www.docker.com/)
[![Kubernetes](https://img.shields.io/badge/kubernetes-ready-326CE5.svg)](https://kubernetes.io/)

**The open-source platform for building, deploying, and orchestrating AI agent systems at scale.**

[🚀 Quick Start](#-quick-start) • [📖 Documentation](https://docs.codetether.run) • [💬 Discord](https://discord.gg/codetether) • [🐦 Twitter](https://twitter.com/codetether)

---

</div>

## 🎯 What is CodeTether?

CodeTether is a **production-ready Agent-to-Agent (A2A) platform** that lets you build AI agent systems that actually work in the real world. Connect any LLM to any tool, orchestrate complex multi-agent workflows, and deploy with confidence.

```
┌─────────────────────────────────────────────────────────────────┐
│                         CodeTether                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │   Claude    │  │   GPT-4     │  │   Gemini    │   LLMs       │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘              │
│         │                │                │                      │
│         └────────────────┼────────────────┘                      │
│                          ▼                                       │
│              ┌───────────────────────┐                           │
│              │    A2A Protocol       │   Standard Communication  │
│              │    Message Broker     │                           │
│              └───────────┬───────────┘                           │
│                          │                                       │
│         ┌────────────────┼────────────────┐                      │
│         ▼                ▼                ▼                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │  OpenCode   │  │ MCP Tools   │  │  Your APIs  │   Actions    │
│  │  (Coding)   │  │  (100+)     │  │             │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
└─────────────────────────────────────────────────────────────────┘
```

## ✨ Why CodeTether?

<table>
<tr>
<td width="50%">

### 🤖 **Multi-Agent Orchestration**
Build systems where agents collaborate, delegate tasks, and share context—all through the standardized A2A protocol.

### 🛠️ **MCP Tool Integration**
Connect to 100+ tools via Model Context Protocol. File systems, databases, APIs, and more.

### 💻 **AI Coding at Scale**
Deploy AI coding agents across your infrastructure using our maintained OpenCode fork. Automated code generation, refactoring, and testing.

### 🔍 **Model Filtering**
Workers automatically filter and register only authenticated models from `auth.json`, ensuring reliable execution.

</td>
<td width="50%">

### 📡 **Real-Time Streaming**
Watch agents think in real-time. SSE streaming for instant feedback and human intervention.

### 🚀 **Production Ready**
Connect workers to `https://api.codetether.run` for live task execution. Helm charts and horizontal scaling included.

### 🔐 **Enterprise Ready**
Keycloak SSO, RBAC, audit logs, and network policies. Security that enterprises demand.

### ☸️ **Deploy Anywhere**
Helm charts, horizontal scaling, blue-green deployments. Production from day one on any cloud or on-premise infrastructure.

</td>
</tr>
</table>

## 🚀 Quick Start

### One-Line Install

```bash
git clone https://github.com/rileyseaburg/codetether.git
cd A2A-Server-MCP && pip install -r requirements.txt
# Optional (recommended): install the package + CLI
pip install -e .

# For production (PostgreSQL persistence):
export DATABASE_URL=postgresql://user:password@host:5432/a2a_server

# Start the server (defaults to `run`)
codetether --port 8000
```

### Docker

```bash
docker run -p 8000:8000 registry.quantum-forge.net/library/a2a-server-mcp:latest
```

### Kubernetes (Production)

```bash
helm install codetether oci://registry.quantum-forge.net/library/a2a-server \
  --namespace codetether --create-namespace
```

### Distributed Workers (Scale Anywhere)

Run agents on any machine with the CodeTether Worker:

```bash
git clone https://github.com/rileyseaburg/codetether.git
cd codetether && sudo ./agent_worker/install.sh
```

Learn more in the [Distributed Workers Guide](https://docs.codetether.run/features/distributed-workers/).

### 🚀 Production Worker Setup

To connect a local worker to the production CodeTether service:

1. **Install the worker**:
   ```bash
   sudo ./agent_worker/install.sh
   ```

2. **Configure for production**:
   Edit `/etc/a2a-worker/env`:
   ```bash
   A2A_SERVER_URL=https://api.codetether.run
   ```

3. **Authenticate models**:
   Ensure your models are authenticated in `~/.local/share/opencode/auth.json`. The worker will only register models it has credentials for.

4. **Restart the service**:
   ```bash
   sudo systemctl restart a2a-agent-worker
   ```
   ```
   # Or use the makefile shortcut:
   make local-worker-restart
   ```

**How it works:**
- Worker discovers local OpenCode sessions from `~/.local/share/opencode/storage/`
- Worker syncs sessions to PostgreSQL via `/v1/opencode/codebases/{id}/sessions/sync`
- Worker syncs session messages via `/v1/opencode/codebases/{id}/sessions/{id}/messages/sync`
- Monitor UI and production API read sessions from PostgreSQL
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
curl -X POST http://localhost:8000/v1/opencode/codebases \
  -H "Content-Type: application/json" \
  -d '{"name": "my-app", "path": "/home/user/my-app"}'

# Trigger an agent task
curl -X POST http://localhost:8000/v1/opencode/codebases/{id}/trigger \
  -d '{"prompt": "Add unit tests for the auth module", "agent": "build"}'
```

### Stream Real-Time Output

```bash
curl http://localhost:8000/v1/opencode/codebases/{id}/events
```

## 🏗️ Architecture

CodeTether is built on **five core pillars**:

| Component | Purpose | Technology |
|-----------|---------|------------|
| **A2A Protocol Server** | Agent communication & orchestration | Python, FastAPI, Redis |
| **Distributed Workers** | Scale agent execution across machines | Python, Redis, Systemd/K8s |
| **MCP Integration** | Tool access & resource management | Model Context Protocol |
| **PostgreSQL Database** | Durable storage for sessions, codebases, tasks | PostgreSQL, asyncpg |
| **OpenCode Bridge** | AI-powered code generation | Local OpenCode fork, Claude/GPT-4 |

### Platform Components

```
codetether/
├── 🌐 API Server          # A2A protocol + REST APIs
├── 🖥️ Monitor UI          # Real-time agent dashboard
├── 👷 [Agent Workers](https://docs.codetether.run/features/distributed-workers/)       # Distributed task execution
├── 🤖 OpenCode Fork       # Maintained AI coding agent
├── 📚 Documentation       # MkDocs Material site
└── 🏠 Marketing Site      # Next.js landing page
```

**Data Flow:**
```
OpenCode Storage (local) → Worker → PostgreSQL → Bridge/API → Monitor UI
```

Workers sync sessions from local OpenCode storage to PostgreSQL. The OpenCode bridge and Monitor UI read from PostgreSQL, providing a consistent view across server replicas and restarts.

## 📦 What's Included

### Core Platform
- ✅ Full A2A Protocol implementation
- ✅ MCP tool integration
- ✅ Redis message broker
- ✅ PostgreSQL durable storage (sessions, codebases, tasks)
- ✅ SSE real-time streaming
- ✅ Worker sync to PostgreSQL from OpenCode storage

### Enterprise Features
- ✅ Keycloak SSO integration
- ✅ Role-based access control
- ✅ Audit logging
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

## 🛠️ Deployment Options

| Environment | Command | Description |
|-------------|---------|-------------|
| **Local** | `python run_server.py` or `make run` | Development mode |
| **Production** | `DATABASE_URL=... make k8s-prod` | Full PostgreSQL persistence |
| **Docker** | `docker-compose up` | Single container |
| **Kubernetes** | `make k8s-prod` | Full production stack |

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

| Variable | Description | Default | Required |
|----------|-------------|---------|------------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@host:5432/db` | Yes (production) |
| `A2A_REDIS_URL` | Redis URL for message broker | `redis://localhost:6379` | No |
| `A2A_AUTH_TOKENS` | Comma-separated auth tokens (format: `name:token,name2:token2`) | `""` | No |
| `OPENCODE_HOST` | Host where OpenCode API is running (container→host) | `localhost` | No |
| `OPENCODE_PORT` | Default OpenCode server port | `9777` | No |
| `A2A_SERVER_URL` | Production server URL (for workers) | `http://localhost:8000` | No |

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
   curl http://localhost:8000/v1/opencode/database/sessions

   # Or via psql:
   psql -d a2a_server -c "SELECT id, codebase_id, title FROM sessions ORDER BY updated_at DESC LIMIT 10;"
   ```

4. **Restart worker to force re-sync:**
   ```bash
   make local-worker-restart
   ```

**How it works:**
- Workers read local OpenCode storage from `~/.local/share/opencode/`
- Workers POST sessions to `/v1/opencode/codebases/{id}/sessions/sync`
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
   curl http://localhost:8000/v1/opencode/database/workers
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

| Resource | Link |
|----------|------|
| 📖 **Full Documentation** | [docs.codetether.run](https://docs.codetether.run) |
| 🚀 **Quick Start Guide** | [Getting Started](https://docs.codetether.run/getting-started/quickstart/) |
| 🔧 **API Reference** | [API Docs](https://docs.codetether.run/api/overview/) |
| 👷 **Agent Worker Guide** | [Agent Worker](https://docs.codetether.run/features/agent-worker/) |
| ☸️ **Kubernetes Deployment** | [Helm Charts](https://docs.codetether.run/deployment/helm/) |
| 🔐 **Authentication** | [Keycloak Setup](https://docs.codetether.run/auth/keycloak/) |

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
