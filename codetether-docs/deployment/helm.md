---
title: Helm Charts
description: Helm chart reference for CodeTether
---

# Helm Charts

CodeTether provides official Helm charts for Kubernetes deployment.

## Installation

```bash
helm repo add codetether https://charts.codetether.run
helm install codetether codetether/a2a-server
```

## Configuration

See `values.yaml` for all configuration options.

### PostgreSQL Configuration

For durable persistence across restarts and replicas, configure an external PostgreSQL database:

```yaml
# values.yaml
externalPostgresql:
  enabled: true
  url: "postgresql://postgres:password@db.example.com:5432/codetether"
```

Or use a Kubernetes secret:

```yaml
externalPostgresql:
  enabled: true
  existingSecret: "codetether-db-secret"
  secretKey: "DATABASE_URL"
```

### Redis Configuration

```yaml
redis:
  enabled: true  # Deploy Redis alongside the server
  # Or use external Redis:
  # url: "redis://:password@redis.example.com:6379"
```

## Upgrading

```bash
helm upgrade codetether codetether/a2a-server
```

## Values Reference

| Key | Default | Description |
|-----|---------|-------------|
| `externalPostgresql.enabled` | `false` | Enable external PostgreSQL |
| `externalPostgresql.url` | — | PostgreSQL connection URL |
| `externalPostgresql.existingSecret` | — | Use existing secret for DATABASE_URL |
| `redis.enabled` | `true` | Deploy Redis |
| `redis.url` | — | External Redis URL |
| `blueGreen.enabled` | `false` | Enable blue-green deployment |
| `replicaCount` | `1` | Number of replicas |
