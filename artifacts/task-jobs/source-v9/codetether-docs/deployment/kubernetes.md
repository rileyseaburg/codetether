---
title: Kubernetes Deployment
description: Deploy CodeTether on Kubernetes
---

# Kubernetes Deployment

Deploy CodeTether Server on Kubernetes using Helm.

## Quick Start

```bash
helm repo add codetether https://charts.codetether.run
helm install codetether codetether/a2a-server \
  --namespace codetether \
  --create-namespace
```

## Values

```yaml
replicaCount: 2

ingress:
  enabled: true
  hosts:
    - host: codetether.example.com
      paths:
        - path: /
          pathType: Prefix

redis:
  enabled: true
```

See [Helm Charts](helm.md) for full configuration.
