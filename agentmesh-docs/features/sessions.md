---
title: Session Management
description: Manage agent sessions with history and resumption
---

# Session Management

AgentMesh provides comprehensive session management for AI agent conversations.

## Features

- **Session History** - View past conversations
- **Session Resumption** - Continue where you left off
- **Cross-device Sync** - Access sessions from anywhere

## API

```bash
# List sessions
GET /v1/opencode/codebases/{id}/sessions

# Sync from OpenCode
POST /v1/opencode/codebases/{id}/sessions/sync
```

See [OpenCode API](../api/opencode.md) for details.
