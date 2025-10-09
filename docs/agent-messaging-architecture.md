# Agent-to-Agent Messaging Architecture

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        A2A Server System                             │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Enhanced A2A Server                               │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │  - Routes incoming A2A protocol messages                    │    │
│  │  - Manages task lifecycle                                   │    │
│  │  - Initializes message broker                               │    │
│  └────────────────────────────────────────────────────────────┘    │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       Message Broker                                 │
│  ┌──────────────────────┐         ┌──────────────────────┐         │
│  │  In-Memory Broker    │   OR    │    Redis Broker      │         │
│  │  (Development)       │         │    (Production)      │         │
│  └──────────────────────┘         └──────────────────────┘         │
│                                                                      │
│  Features:                                                           │
│  • Publish/Subscribe pattern                                        │
│  • Direct message routing                                           │
│  • Event aggregation                                                │
│  • Subscription management                                          │
└──────────────┬───────────────────────────────────┬──────────────────┘
               │                                   │
        ┌──────┴──────┐                    ┌──────┴──────┐
        ▼             ▼                    ▼             ▼
┌─────────────┐ ┌─────────────┐    ┌─────────────┐ ┌─────────────┐
│  Agent A    │ │  Agent B    │    │  Agent C    │ │  Agent D    │
└─────────────┘ └─────────────┘    └─────────────┘ └─────────────┘
```

## Message Flow Diagrams

### 1. Direct Messaging Flow

```
┌──────────┐                                      ┌──────────┐
│ Agent A  │                                      │ Agent B  │
└─────┬────┘                                      └─────┬────┘
      │                                                 │
      │ 1. send_message_to_agent("Agent B", msg)       │
      │─────────────────────────────────────────►      │
      │                                                 │
      │         ┌──────────────────┐                   │
      │         │ Message Broker   │                   │
      │         │                  │                   │
      │         │ Routes message   │                   │
      │         │ to Agent B       │                   │
      │         └──────────────────┘                   │
      │                                                 │
      │              2. Message delivered               │
      │              via message broker                 │
      │─────────────────────────────────────────────────►
      │                                                 │
      │                              3. process_message()│
      │                                                 │
      │              4. Response message                │
      │◄─────────────────────────────────────────────────
      │                                                 │
```

### 2. Event Publishing Flow

```
┌──────────┐                                                ┌──────────┐
│Publisher │                                                │Subscriber│
└─────┬────┘                                                └────┬─────┘
      │                                                          │
      │ 1. publish_event("data.ready", data)                    │
      │─────────────────────────────────────────────►           │
      │                                                          │
      │         ┌──────────────────────────────┐                │
      │         │      Message Broker          │                │
      │         │                              │                │
      │         │  • Receives event            │                │
      │         │  • Finds subscribers         │                │
      │         │  • Notifies all handlers     │                │
      │         └──────────────────────────────┘                │
      │                                                          │
      │                  2. Event notification                   │
      │──────────────────────────────────────────────────────────►
      │                                                          │
      │                               3. handler(event_type, data)│
      │                                                          │
```

### 3. Multi-Agent Coordination Flow

```
┌──────────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│ Coordinator  │     │ Worker 1 │     │ Worker 2 │     │ Monitor  │
└──────┬───────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘
       │                  │                 │                 │
       │ 1. Distribute work                 │                 │
       │──────────────────►                 │                 │
       │                  │                 │                 │
       │                  │ 2. Distribute work                │
       │──────────────────┼─────────────────►                 │
       │                  │                 │                 │
       │ 3. Publish coordination event                        │
       │──────────────────┼─────────────────┼─────────────────►
       │                  │                 │                 │
       │  4. Process      │                 │                 │
       │◄─────────────────                  │                 │
       │                  │  5. Process      │                 │
       │                  │◄─────────────────                 │
       │                  │                 │                 │
       │                  │ 6. Publish "task.complete"        │
       │                  │──────────────────┼─────────────────►
       │                  │                 │                 │
       │                  │                 │ 7. Publish "task.complete"
       │                  │                 │─────────────────►
       │                  │                 │                 │
       │                  │                 │    8. Aggregate │
       │                  │                 │       results   │
       │                  │                 │                 │
```

## Agent Communication Patterns

### Pattern 1: Request-Response

```
Agent A  ──send_message──►  Agent B
         ◄───response─────
```

**Use Case**: When you need a specific agent to process something and return a result.

**Example**: Coordinator asks Calculator to perform a calculation.

### Pattern 2: Publish-Subscribe

```
Publisher  ──publish_event──►  Message Broker
                                      │
                      ┌───────────────┼───────────────┐
                      ▼               ▼               ▼
                Subscriber 1    Subscriber 2    Subscriber 3
```

**Use Case**: When multiple agents need to be notified of state changes.

**Example**: Data processor publishes "processing.complete" event, multiple monitoring agents subscribe.

### Pattern 3: Pipeline

```
Agent A ──►  Agent B  ──►  Agent C  ──►  Agent D
(Stage 1)    (Stage 2)     (Stage 3)     (Stage 4)
```

**Use Case**: Sequential processing where each agent performs one stage.

**Example**: Data collection → Processing → Analysis → Reporting

### Pattern 4: Aggregator

```
        Agent A ──┐
        Agent B ──┼──►  Aggregator Agent
        Agent C ──┘
```

**Use Case**: Collecting data/events from multiple sources.

**Example**: Aggregator collects results from multiple data sources.

### Pattern 5: Coordinator-Worker

```
Coordinator ──┬──►  Worker 1
              ├──►  Worker 2
              └──►  Worker 3
```

**Use Case**: Distributing work across multiple workers.

**Example**: Load balancing tasks across worker agents.

### Pattern 6: Hierarchical

```
        Manager
          │
    ┌─────┼─────┐
    ▼     ▼     ▼
  Team  Team  Team
  Lead  Lead  Lead
    │     │     │
  ┌─┼─┐ ┌─┼─┐ ┌─┼─┐
  W W W W W W W W W
```

**Use Case**: Multi-level organization with delegation.

**Example**: Manager delegates to team leads who delegate to workers.

## Component Interaction

### EnhancedAgent Internal Flow

```
┌────────────────────────────────────────────────────┐
│                 EnhancedAgent                       │
│                                                     │
│  ┌──────────────────────────────────────────────┐  │
│  │  Public Methods                               │  │
│  │  • send_message_to_agent()                   │  │
│  │  • publish_event()                           │  │
│  │  • subscribe_to_agent_events()               │  │
│  │  • process_message()                         │  │
│  └──────────────┬───────────────────────────────┘  │
│                 │                                   │
│                 ▼                                   │
│  ┌──────────────────────────────────────────────┐  │
│  │  Internal Methods                             │  │
│  │  • _handle_incoming_message()                │  │
│  │  • _extract_text_content()                   │  │
│  │  • subscribe_to_messages()                   │  │
│  └──────────────┬───────────────────────────────┘  │
│                 │                                   │
│                 ▼                                   │
│  ┌──────────────────────────────────────────────┐  │
│  │  State                                        │  │
│  │  • message_broker                            │  │
│  │  • _message_handlers                         │  │
│  │  • mcp_client                                │  │
│  └──────────────────────────────────────────────┘  │
│                                                     │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
            ┌──────────────────┐
            │ Message Broker   │
            └──────────────────┘
```

## Message Format

### Direct Message

```json
{
  "event_type": "message.to.{agent_name}",
  "data": {
    "from_agent": "Sender Agent",
    "to_agent": "Receiver Agent",
    "message": {
      "parts": [
        {
          "type": "text",
          "content": "Message content"
        }
      ]
    },
    "timestamp": "2025-10-02T12:00:00Z"
  }
}
```

### Published Event

```json
{
  "event_type": "agent.{agent_name}.{event_type}",
  "data": {
    "agent": "Publisher Agent",
    "event_type": "custom.event",
    "data": {
      "key": "value",
      "timestamp": "2025-10-02T12:00:00Z"
    },
    "timestamp": "2025-10-02T12:00:00Z"
  }
}
```

## Scalability Considerations

### Horizontal Scaling with Redis

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ A2A Server 1│     │ A2A Server 2│     │ A2A Server 3│
│             │     │             │     │             │
│  Agents A-C │     │  Agents D-F │     │  Agents G-I │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       └───────────────────┼───────────────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │  Redis Cluster  │
                  │  (Message Bus)  │
                  └─────────────────┘
```

**Benefits:**
- Agents across different servers can communicate
- Load distribution
- Fault tolerance
- Persistence of messages

## Error Handling Flow

```
Agent sends message
       │
       ▼
┌──────────────┐
│ Try sending  │
└──────┬───────┘
       │
       ├──Success──► Message delivered
       │
       └──Error────► Log error
                     │
                     ▼
              Continue execution
              (No crash)
```

## Summary

The agent-to-agent messaging architecture provides:

1. **Flexible Communication**: Direct messages, pub/sub, and hybrid patterns
2. **Scalability**: From in-memory to Redis cluster
3. **Reliability**: Error handling and graceful degradation
4. **Simplicity**: Clean API for agent developers
5. **Production Ready**: Battle-tested message broker patterns

This architecture enables sophisticated multi-agent systems while keeping the implementation clean and maintainable.
