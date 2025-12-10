---
title: Kubernetes Deployment
description: Deploy AgentMesh on Kubernetes
---

# Kubernetes Deployment

Deploy AgentMesh Server on Kubernetes using Helm.

## Quick Start

```bash
helm repo add agentmesh https://charts.agentmesh.run
helm install agentmesh agentmesh/a2a-server \
  --namespace agentmesh \
  --create-namespace
```

## Values

```yaml
replicaCount: 2

ingress:
  enabled: true
  hosts:
    - host: agentmesh.example.com
      paths:
        - path: /
          pathType: Prefix

redis:
  enabled: true
```

See [Helm Charts](helm.md) for full configuration.
