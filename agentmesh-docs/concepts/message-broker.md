---
title: Message Broker
description: Redis-based message broker for distributed agent communication
---

# Message Broker

CodeTether uses Redis as a message broker for distributed agent communication and task queuing.

## Overview

The message broker enables:

- **Task Distribution** - Route tasks to appropriate workers
- **Pub/Sub Messaging** - Real-time event distribution
- **State Synchronization** - Share state across instances

## Configuration

```bash
export A2A_REDIS_URL=redis://localhost:6379
```

## Redis Requirements

- Redis 6.0 or later
- Recommended: Redis Cluster for high availability

## Message Channels

| Channel | Purpose |
|---------|---------|
| `a2a:tasks` | Task queue |
| `a2a:events` | Real-time events |
| `a2a:agents` | Agent status updates |

## Next Steps

- [Architecture](architecture.md)
- [Distributed Workers](../features/distributed-workers.md)
