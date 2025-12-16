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
Deploy OpenCode agents across your infrastructure. Automated code generation, refactoring, and testing.

</td>
<td width="50%">

### 📡 **Real-Time Streaming**
Watch agents think in real-time. SSE streaming for instant feedback and human intervention.

### 🔐 **Enterprise Ready**
Keycloak SSO, RBAC, audit logs, and network policies. Security that enterprises demand.

### ☸️ **Cloud Native**
Helm charts, horizontal scaling, blue-green deployments. Production from day one.

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

CodeTether is built on **three core pillars**:

| Component | Purpose | Technology |
|-----------|---------|------------|
| **A2A Protocol Server** | Agent communication & orchestration | Python, FastAPI, Redis |
| **MCP Integration** | Tool access & resource management | Model Context Protocol |
| **OpenCode Bridge** | AI-powered code generation | OpenCode, Claude/GPT-4 |

### Platform Components

```
codetether/
├── 🌐 API Server          # A2A protocol + REST APIs
├── 🖥️ Monitor UI          # Real-time agent dashboard
├── 👷 Agent Workers       # Distributed task execution
├── 📚 Documentation       # MkDocs Material site
└── 🏠 Marketing Site      # Next.js landing page
```

## 📦 What's Included

### Core Platform
- ✅ Full A2A Protocol implementation
- ✅ MCP tool integration
- ✅ Redis message broker
- ✅ SSE real-time streaming
- ✅ Session persistence & resumption

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
| **Local** | `python run_server.py` | Development mode |
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

# Start development server
python run_server.py --port 8000
```

## 📄 License

Apache License 2.0 - See [LICENSE](LICENSE) for details.

---

<div align="center">

**Built with ❤️ by the CodeTether Team**

[Website](https://codetether.run) • [Documentation](https://docs.codetether.run) • [GitHub](https://github.com/rileyseaburg/codetether)

</div>
