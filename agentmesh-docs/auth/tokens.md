---
title: API Tokens
description: Configure API token authentication
---

# API Tokens

Simple bearer token authentication for AgentMesh.

## Setup

```bash
export A2A_AUTH_ENABLED=true
export A2A_AUTH_TOKENS="admin:token1,worker:token2"
```

## Usage

```bash
curl -H "Authorization: Bearer token1" \
  https://agentmesh.example.com/v1/a2a
```

## Multiple Tokens

Define multiple named tokens:

```bash
A2A_AUTH_TOKENS="admin:super-secret,readonly:read-only-token,worker:worker-token"
```
