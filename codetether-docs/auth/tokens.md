---
title: API Tokens
description: Configure API token authentication
---

# API Tokens

Simple bearer token authentication for CodeTether.

## Setup

```bash
export A2A_AUTH_ENABLED=true
export A2A_AUTH_TOKENS="admin:token1,worker:token2"
```

## Usage

```bash
curl -X POST https://codetether.example.com/v1/a2a \
  -H "Authorization: Bearer token1" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "message/send",
    "params": {
      "message": {
        "parts": [{"type": "text", "content": "Hello"}]
      }
    },
    "id": "1"
  }'
```

## Multiple Tokens

Define multiple named tokens:

```bash
A2A_AUTH_TOKENS="admin:super-secret,readonly:read-only-token,worker:worker-token"
```
