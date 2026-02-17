---
title: Docker Deployment
description: Deploy CodeTether with Docker
---

# Docker Deployment

Deploy CodeTether Server using Docker.

## Quick Start

```bash
docker run -d \
  --name codetether \
  -p 8000:8000 \
  -p 9000:9000 \
  ghcr.io/rileyseaburg/codetether-server:latest
```

## Connecting to Host CodeTether

When running CodeTether in Docker and you want to connect to CodeTether running on your host machine:

### Docker Desktop (Mac/Windows)

```bash
docker run -d \
  --name codetether \
  -p 8000:8000 \
  -p 9000:9000 \
  -e OPENCODE_HOST=host.docker.internal \
  -e OPENCODE_PORT=9777 \
  ghcr.io/rileyseaburg/codetether-server:latest
```

### Linux

```bash
docker run -d \
  --name codetether \
  --add-host=host.docker.internal:host-gateway \
  -p 8000:8000 \
  -p 9000:9000 \
  -e OPENCODE_HOST=host.docker.internal \
  -e OPENCODE_PORT=9777 \
  ghcr.io/rileyseaburg/codetether-server:latest
```

### Using Host IP

```bash
docker run -d \
  --name codetether \
  -p 8000:8000 \
  -p 9000:9000 \
  -e OPENCODE_HOST=192.168.1.100 \
  -e OPENCODE_PORT=9777 \
  ghcr.io/rileyseaburg/codetether-server:latest
```

## Docker Compose

```yaml
version: '3.8'
services:
  codetether:
    image: ghcr.io/rileyseaburg/codetether-server:latest
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
