---
title: Docker Deployment
description: Deploy AgentMesh with Docker
---

# Docker Deployment

Deploy AgentMesh Server using Docker.

## Quick Start

```bash
docker run -d \
  --name agentmesh \
  -p 8000:8000 \
  -p 9000:9000 \
  ghcr.io/rileyseaburg/agentmesh-server:latest
```

## Connecting to Host OpenCode

When running AgentMesh in Docker and you want to connect to OpenCode running on your host machine:

### Docker Desktop (Mac/Windows)

```bash
docker run -d \
  --name agentmesh \
  -p 8000:8000 \
  -p 9000:9000 \
  -e OPENCODE_HOST=host.docker.internal \
  -e OPENCODE_PORT=9777 \
  ghcr.io/rileyseaburg/agentmesh-server:latest
```

### Linux

```bash
docker run -d \
  --name agentmesh \
  --add-host=host.docker.internal:host-gateway \
  -p 8000:8000 \
  -p 9000:9000 \
  -e OPENCODE_HOST=host.docker.internal \
  -e OPENCODE_PORT=9777 \
  ghcr.io/rileyseaburg/agentmesh-server:latest
```

### Using Host IP

```bash
docker run -d \
  --name agentmesh \
  -p 8000:8000 \
  -p 9000:9000 \
  -e OPENCODE_HOST=192.168.1.100 \
  -e OPENCODE_PORT=9777 \
  ghcr.io/rileyseaburg/agentmesh-server:latest
```

## Docker Compose

```yaml
version: '3.8'
services:
  agentmesh:
    image: ghcr.io/rileyseaburg/agentmesh-server:latest
    ports:
      - "8000:8000"
      - "9000:9000"
    environment:
      - A2A_REDIS_URL=redis://redis:6379
      - OPENCODE_HOST=host.docker.internal
      - OPENCODE_PORT=9777
    extra_hosts:
      - "host.docker.internal:host-gateway"  # For Linux
    depends_on:
      - redis
  redis:
    image: redis:7-alpine
```

See [Installation](../getting-started/installation.md) for more options.
