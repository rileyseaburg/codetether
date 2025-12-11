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

## Upgrading

```bash
helm upgrade codetether codetether/a2a-server
```
