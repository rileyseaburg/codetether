---
title: Session Management
description: Manage agent sessions with history and resumption
---

# Session Management

CodeTether provides comprehensive session management for AI agent conversations.

## Features

- **Session History** - View past conversations
- **Session Resumption** - Continue where you left off
- **Cross-device Sync** - Access sessions from anywhere

## API

```bash
# List sessions
GET /v1/agent/codebases/{id}/sessions

# Sync from CodeTether
POST /v1/agent/codebases/{id}/sessions/sync
```

See [CodeTether API](../api/agent.md) for details.
