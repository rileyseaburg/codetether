---
title: Installation
description: Install CodeTether Server via pip, Docker, or from source
---

# Installation

CodeTether Server can be installed in several ways depending on your needs.

## Requirements

- Python 3.10+ (for pip install)
- Docker 20.10+ (for container deployment)
- Redis 6+ (optional, for distributed workers)

## Install via pip (recommended)

If you have a Python environment already set up, pip is the simplest option.

```bash
pip install codetether
```

Verify the installation:

```bash
codetether --version
# 1.0.0
```

### Install from GitHub (pip)

If you want the latest code (or you're installing before a PyPI release is published):

```bash
pip install "git+https://github.com/rileyseaburg/codetether.git@main"
```

## One-line install (shell)

This installs CodeTether into a local virtual environment under `~/.codetether/venv`
and links the CLI into `~/.local/bin`.

```bash
curl -fsSL https://raw.githubusercontent.com/rileyseaburg/codetether/main/scripts/install-codetether.sh | bash
```

## Docker

Pull the official image:

```bash
docker pull ghcr.io/rileyseaburg/codetether-server:latest
```

Run the server:

```bash
docker run -d \
  --name codetether \
  -p 8000:8000 \
  -p 9000:9000 \
  ghcr.io/rileyseaburg/codetether-server:latest
```

With environment configuration:

```bash
docker run -d \
  --name codetether \
  -p 8000:8000 \
  -p 9000:9000 \
  -e A2A_AGENT_NAME="My Agent" \
  -e REDIS_URL="redis://redis:6379" \
  -e KEYCLOAK_URL="https://auth.example.com" \
  ghcr.io/rileyseaburg/codetether-server:latest
```

## Docker Compose

Create a `docker-compose.yml`:

```yaml
version: '3.8'

services:
  codetether:
    image: ghcr.io/rileyseaburg/codetether-server:latest
    ports:
      - "8000:8000"  # A2A API
      - "9000:9000"  # MCP Server
    environment:
      - A2A_AGENT_NAME=CodeTether Server
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
git clone https://github.com/rileyseaburg/codetether.git
cd codetether
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
codetether --port 8000
```

## OpenCode (Local Fork)

CodeTether includes a maintained fork of OpenCode in the `opencode/` directory. To build it:

```bash
cd opencode

# Install dependencies
bun install

# Build the project
bun run build

# Verify installation
opencode --version
```

For more details, see [OpenCode Integration](../features/opencode.md).

## Agent Worker (systemd, Linux)

To execute OpenCode tasks on machines that host codebases, install the agent worker.
First ensure you have [built OpenCode from the local fork](#opencode-local-fork).

```bash
git clone https://github.com/rileyseaburg/codetether.git
cd codetether

sudo ./agent_worker/install.sh
sudo systemctl start a2a-agent-worker
sudo journalctl -u a2a-agent-worker -f
```

## Kubernetes (Helm)

Add the Helm repository:

```bash
helm repo add codetether https://charts.codetether.run
helm repo update
```

Install the chart:

```bash
helm install codetether codetether/a2a-server \
  --namespace codetether \
  --create-namespace \
  --set ingress.enabled=true \
  --set ingress.hosts[0].host=codetether.example.com
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
