# CodeTether Integration

Connect AI coding agents to the CodeTether Server for seamless agent-to-agent communication and task orchestration.

## Overview

The CodeTether integration allows external AI coding agents (like Claude, GPT-4, or custom agents) to connect to the CodeTether Server using the A2A Protocol. This enables:

- **Task Submission** — Agents can submit tasks to the server for processing
- **Real-time Streaming** — Receive live updates on task progress via SSE
- **Session Management** — Maintain context across multiple interactions
- **Capability Discovery** — Agents can discover available skills and tools

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `CODETETHER_AGENT_ENABLED` | Enable agent integration | `0` |
| `CODETETHER_AGENT_ID` | Unique agent identifier | Auto-generated |
| `CODETETHER_RLM_ENABLED` | Enable RLM support | `0` |

### Agent Card

Agents should expose an agent card at `/.well-known/agent-card.json`:

```json
{
  "name": "CodeTether Agent",
  "description": "AI coding agent connected to CodeTether Server",
  "url": "https://api.codetether.run",
  "version": "1.0.0",
  "capabilities": {
    "streaming": true,
    "pushNotifications": true,
    "stateTransition": true
  },
  "skills": [
    {
      "id": "code-review",
      "name": "Code Review",
      "description": "Review code for bugs and improvements"
    }
  ]
}
```

## RLM (Recursive Language Models)

RLM enables processing arbitrarily large codebases without context limits by recursively analyzing code structure.

### How It Works

1. **Codebase Analysis** — RLM breaks down the codebase into manageable chunks
2. **Dependency Mapping** — Understands imports and dependencies between files
3. **Contextual Processing** — Processes files with their relevant context
4. **Result Aggregation** — Combines results from multiple analyses

### Enabling RLM

```bash
export CODETETHER_RLM_ENABLED=1
export CODETETHER_RLM_MODEL=local_cuda/qwen3-4b
```

### RLM Commands

```bash
# Analyze a codebase
codetether rlm --model local_cuda/qwen3-4b --file src/main.rs

# Process with JSON output
codetether rlm --model local_cuda/qwen3-4b --file src/ --json

# Interactive REPL
codetether rlm --model local_cuda/qwen3-4b --repl
```

### RLM Events

When using RLM, the following SSE events are emitted:

| Event | Description |
|-------|-------------|
| `rlm.step` | Current processing step |
| `rlm.stats` | Statistics (tokens, chunks, subcalls) |
| `rlm.routing` | Routing decisions for code analysis |

```typescript
interface RLMStep {
  id: string;
  type: 'load' | 'code' | 'output' | 'subcall' | 'result' | 'error';
  content: string;
  timestamp: number;
  status: 'pending' | 'running' | 'completed' | 'failed';
  duration?: number;
}

interface RLMStats {
  tokens: number;
  chunks: number;
  subcalls: {
    completed: number;
    total: number;
  };
}
```

## Connecting Your Agent

### Step 1: Register Your Agent

```python
from a2a_client import A2AClient

client = A2AClient('https://api.codetether.run')

# Register agent capabilities
await client.register_agent({
    'name': 'My AI Agent',
    'capabilities': ['streaming', 'pushNotifications']
})
```

### Step 2: Submit Tasks

```python
# Submit a coding task
task = await client.create_task({
    'description': 'Implement user authentication',
    'skills': ['coding', 'security'],
    'sessionId': 'user-session-123'
})

# Stream results
async for event in task.stream():
    print(event)
```

### Step 3: Handle Responses

```python
# Get final result
result = await task.get_result()
print(result.artifacts)
```

## Best Practices

1. **Use Sessions** — Maintain context with session IDs for multi-turn conversations
2. **Enable Streaming** — Subscribe to SSE for real-time progress updates
3. **Handle Errors** — Implement retry logic for failed tasks
4. **Cache Agent Card** — Cache the agent card to reduce API calls

## See Also

- [A2A Protocol](../concepts/a2a-protocol.md)
- [JSON-RPC Methods](../api/jsonrpc.md)
- [SSE Events](../api/sse.md)
- [Ralph (Autonomous Dev)](./ralph.md)
