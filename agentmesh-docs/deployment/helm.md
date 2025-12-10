---
title: Helm Charts
description: Helm chart reference for AgentMesh
---

# Helm Charts

AgentMesh provides official Helm charts for Kubernetes deployment.

## Installation

```bash
helm repo add agentmesh https://charts.agentmesh.run
helm install agentmesh agentmesh/a2a-server
```

## Configuration

See `values.yaml` for all configuration options.

## Upgrading

```bash
helm upgrade agentmesh agentmesh/a2a-server
```
