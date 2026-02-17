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

## Agent-Targeted Routing (v0.7.0+)

### Overview

Agent-targeted routing enables tasks to be sent to specific named agents rather than any available worker. This is essential for specialized workflows where certain agents have unique capabilities.

### Routing Flow

```
┌──────────┐                                      ┌──────────────┐
│  Client  │                                      │ Target Agent │
└─────┬────┘                                      └──────┬───────┘
      │                                                   │
      │ 1. send_to_agent(agent_name="code-reviewer")     │
      │─────────────────────────────────────────►        │
      │                                                   │
      │         ┌────────────────────────┐               │
      │         │    A2A Server          │               │
      │         │                        │               │
      │         │ • Stores target_agent  │               │
      │         │ • SSE notifies only    │               │
      │         │   matching workers     │               │
      │         │ • SQL claim verifies   │               │
      │         │   agent name match     │               │
      │         └────────────────────────┘               │
      │                                                   │
      │              2. Task queued for agent             │
      │                                                   │
      │                   3. Worker with agent_name       │
      │                      "code-reviewer" claims       │
      │                                                   │
      │              4. Task executed                     │
      │◄─────────────────────────────────────────────────│
      │                                                   │
```

### New MCP Tools

#### `send_message_async` - Fire-and-Forget Async Messaging

```json
{
    "tool": "send_message_async",
    "params": {
        "message": "Process this data",
        "conversation_id": "conv-123",
        "codebase_id": "my-project",
        "priority": 5,
        "notify_email": "user@example.com"
    }
}
```

Returns immediately with `task_id` and `run_id`. Any available worker can claim the task.

#### `send_to_agent` - Agent-Targeted Routing

```json
{
    "tool": "send_to_agent",
    "params": {
        "agent_name": "code-reviewer",
        "message": "Review this PR",
        "deadline_seconds": 300,
        "priority": 10
    }
}
```

Routes to a specific named agent. Task queues indefinitely by default unless `deadline_seconds` is set.

### Capability-Based Routing

Workers can declare capabilities, and tasks can require specific capabilities:

```bash
# Start worker with agent name and capabilities
codetether-worker --agent-name=code-reviewer --capabilities=python,pytest,security
```

```json
{
    "tool": "send_to_agent",
    "params": {
        "agent_name": "code-reviewer",
        "message": "Review security-sensitive code",
        "required_capabilities": ["python", "security"]
    }
}
```

The worker must have ALL required capabilities (AND logic).

### Routing Behavior

| Scenario                        | Behavior                     |
| ------------------------------- | ---------------------------- |
| No target agent                 | Any worker can claim         |
| Target agent online             | Only that agent claims       |
| Target agent offline            | Queue indefinitely (default) |
| Target agent offline + deadline | Fail after deadline          |
| Required capabilities not met   | Task skipped by worker       |

### Dual-Layer Enforcement

1. **SSE Layer (Notify-time)**: Workers only receive notifications for tasks they can claim
2. **SQL Layer (Claim-time)**: Atomic claim query verifies agent name and capabilities

This ensures no race conditions and prevents tasks from being claimed by the wrong worker.

## RLM (Recursive Language Models)

### Overview

RLM enables agents to process arbitrarily long contexts by treating prompts as external environment variables in a Python REPL. This bridges the gap between large codebases and limited context windows.

### Architecture

```
┌─────────────────────┐                ┌─────────────────────────────┐
│ A2A Server (Python) │                │ CodeTether Worker (TypeScript)│
├─────────────────────┤   dispatch     ├─────────────────────────────┤
│ Task with:          │ ────────────>  │ RLM Tool                    │
│ - model_ref         │                │ ┌─────────────────────────┐ │
│ - subcall_model_ref │                │ │ Python REPL             │ │
│                     │                │ │ - context variable      │ │
│ ModelResolver:      │                │ │ - llm_query() bridge    │ │
│ - Fallback chain    │                │ └───────────┬─────────────┘ │
│ - Controller allow  │                │             │ subcalls      │
└─────────────────────┘                │             ▼               │
                                       │ ┌─────────────────────────┐ │
                                       │ │ Sub-LLM (configurable)  │ │
                                       │ └─────────────────────────┘ │
                                       └─────────────────────────────┘
```

### Model Resolution Flow

```
                    ┌─────────────────┐
                    │   Task Input    │
                    │ subcall_model_ref│
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ Explicit ref?   │──Yes──► Use task.subcall_model_ref
                    └────────┬────────┘
                             │ No
                    ┌────────▼────────┐
                    │ Default config? │──Yes──► Use A2A_RLM_DEFAULT_SUBCALL_MODEL_REF
                    └────────┬────────┘
                             │ No
                    ┌────────▼────────┐
                    │ Check fallback  │──Match──► Use first matching model
                    │ chain           │           from fallback chain
                    └────────┬────────┘
                             │ No match
                    ┌────────▼────────┐
                    │ Controller      │──Yes──► Use controller's model
                    │ fallback ok?    │
                    └────────┬────────┘
                             │ No
                    ┌────────▼────────┐
                    │ NoEligibleModel │
                    │ Error           │
                    └─────────────────┘
```

### RLM Execution Flow

```
┌──────────────┐
│ RLM Tool     │
│ receives task│
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Create Python│
│ REPL process │
└──────┬───────┘
       │
       ▼
┌──────────────┐      ┌─────────────────┐
│ Load context │ ───► │ context variable│
│ into REPL    │      │ available       │
└──────┬───────┘      └─────────────────┘
       │
       ▼
┌──────────────┐
│ Execute LLM  │◄────────────────────────┐
│ generated    │                         │
│ Python code  │                         │
└──────┬───────┘                         │
       │                                 │
       ├── llm_query() ──► Sub-LLM call ─┘
       │
       ├── FINAL() ──► Return result
       │
       └── No FINAL ──► Next iteration
```

### Guardrails

| Guardrail                  | Default | Purpose                                    |
| -------------------------- | ------- | ------------------------------------------ |
| MAX_SUBCALLS_PER_ITERATION | 5       | Prevent infinite loops in single iteration |
| MAX_TOTAL_SUBCALLS         | 100     | Limit total LLM calls per session          |
| MAX_SUBCALL_TOKENS         | 8000    | Prevent context explosion in subcalls      |
| MAX_ITERATIONS             | 20      | Limit total Python code iterations         |

### Environment Variables

```bash
# A2A Server (Model Resolution)
A2A_RLM_DEFAULT_SUBCALL_MODEL_REF="zai:glm-4.7"
A2A_RLM_FALLBACK_CHAIN="zai:glm-4.7,openai:gpt-4o-mini,controller"
A2A_RLM_ALLOW_CONTROLLER_FALLBACK=1

# CodeTether Worker (Guardrails)
A2A_RLM_MAX_SUBCALLS_PER_ITERATION=5
A2A_RLM_MAX_TOTAL_SUBCALLS=100
A2A_RLM_MAX_SUBCALL_TOKENS=8000
A2A_RLM_MAX_ITERATIONS=20

# Worker Capability
OPENCODE_RLM_ENABLED=1
```

## Summary

The agent-to-agent messaging architecture provides:

1. **Flexible Communication**: Direct messages, pub/sub, and hybrid patterns
2. **Scalability**: From in-memory to Redis cluster
3. **Reliability**: Error handling and graceful degradation
4. **Simplicity**: Clean API for agent developers
5. **Production Ready**: Battle-tested message broker patterns
6. **Targeted Routing**: Route tasks to specific named agents with capability matching
7. **RLM Support**: Process arbitrarily long contexts through recursive LLM calls

This architecture enables sophisticated multi-agent systems while keeping the implementation clean and maintainable.
