---
title: Installation
description: Install AgentMesh Server via pip, Docker, or from source
---

# Installation

AgentMesh Server can be installed in several ways depending on your needs.

## Requirements

- Python 3.10+ (for pip install)
- Docker 20.10+ (for container deployment)
- Redis 6+ (optional, for distributed workers)

## Quick Install (pip)

```bash
pip install a2a-server-mcp
```

Verify the installation:

```bash
agentmesh --version
# AgentMesh Server v1.0.0
```

## Docker

Pull the official image:

```bash
docker pull ghcr.io/rileyseaburg/agentmesh-server:latest
```

Run the server:

```bash
docker run -d \
  --name agentmesh \
  -p 8000:8000 \
  -p 9000:9000 \
  ghcr.io/rileyseaburg/agentmesh-server:latest
```

With environment configuration:

```bash
docker run -d \
  --name agentmesh \
  -p 8000:8000 \
  -p 9000:9000 \
  -e A2A_AGENT_NAME="My Agent" \
  -e REDIS_URL="redis://redis:6379" \
  -e KEYCLOAK_URL="https://auth.example.com" \
  ghcr.io/rileyseaburg/agentmesh-server:latest
```

## Docker Compose

Create a `docker-compose.yml`:

```yaml
version: '3.8'

services:
  agentmesh:
    image: ghcr.io/rileyseaburg/agentmesh-server:latest
    ports:
      - "8000:8000"  # A2A API
      - "9000:9000"  # MCP Server
    environment:
      - A2A_AGENT_NAME=AgentMesh Server
      - REDIS_URL=redis://redis:6379
      - LOG_LEVEL=INFO
    depends_on:
      - redis

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data

volumes:
  redis-data:
```

Start the stack:

```bash
docker-compose up -d
```

## From Source

Clone the repository:

```bash
git clone https://github.com/rileyseaburg/A2A-Server-MCP.git
cd A2A-Server-MCP
```

Create a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or
.\venv\Scripts\activate   # Windows
```

Install dependencies:

```bash
pip install -e .
```

Run the server:

```bash
python run_server.py run --port 8000
```

## Kubernetes (Helm)

Add the Helm repository:

```bash
helm repo add agentmesh https://charts.agentmesh.run
helm repo update
```

Install the chart:

```bash
helm install agentmesh agentmesh/a2a-server \
  --namespace agentmesh \
  --create-namespace \
  --set ingress.enabled=true \
  --set ingress.hosts[0].host=agentmesh.example.com
```

See [Kubernetes Deployment](../deployment/kubernetes.md) for full configuration options.

## Verify Installation

Once installed, verify the server is running:

```bash
# Check health endpoint
curl http://localhost:8000/health
# {"status": "healthy", "version": "1.0.0"}

# Check agent card (A2A discovery)
curl http://localhost:8000/.well-known/agent-card.json
```

## Next Steps

- [Quick Start](quickstart.md) — Run your first agent task
- [Configuration](configuration.md) — Configure authentication, Redis, and more
- [OpenCode Integration](../features/opencode.md) — Set up AI coding agents
