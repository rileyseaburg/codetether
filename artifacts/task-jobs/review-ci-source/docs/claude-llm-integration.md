# Claude LLM Integration with Agent-to-Agent Messaging

## Overview

The A2A Server now includes a **Claude LLM Agent** that integrates with your local Anthropic-compatible API (localhost:4000) and participates fully in the agent-to-agent messaging system.

## Features

✅ **Direct LLM Integration** - Connects to Claude via Anthropic API
✅ **Agent-to-Agent Communication** - Fully integrated with message broker
✅ **Intelligent Routing** - Uses Claude to make smart routing decisions
✅ **Multi-Agent Coordination** - Combines Claude with Calculator, Memory, and Analysis agents
✅ **Workflow Orchestration** - Plans and coordinates complex multi-step tasks

## Quick Start

### Run the Demo

```bash
# Make sure your LLM API is running on localhost:4000
python examples/claude_agent.py
```

### Interactive Session

```bash
python examples/claude_agent.py --interactive
```

## Demo Output

The demo showcases 4 powerful scenarios:

### Demo 1: Simple Question to Claude

```
Question: What are the key benefits of agent-to-agent communication?

Claude's Response:
# Key Benefits of Agent-to-Agent Communication

1. **Specialization & Expertise** - Each agent focuses on specific tasks
2. **Scalability** - Distribute workload across multiple agents
3. **Modularity & Maintenance** - Easier to update or replace individual agents
4. **Parallel Processing** - Multiple agents work simultaneously
5. **Resource Efficiency** - Delegate tasks to optimized agents
6. **Enhanced Problem-Solving** - Combine different perspectives
7. **Flexibility** - Add new capabilities without redesigning
```

### Demo 2: Claude + Calculator Coordination

```
Calculator: Calculation: 1234 * 567 = 699678

Claude's Explanation:
Let me break down this multiplication in an interesting way:

1234 × 567 = 699,678

Think of this as combining:
- 1234 groups of 567, or
- 567 groups of 1234

The result is just under 700,000 - specifically 322 away from 700,000!
```

### Demo 3: Claude-Powered Intelligent Router

Claude makes routing decisions for incoming requests:

```
Request: "What is 789 + 456?"
🧠 Claude's routing decision: Calculator Agent - straightforward arithmetic calculation
→ Routed to Calculator Agent

Request: "Store the fact that our system uses Redis for message brokering"
🧠 Claude's routing decision: Memory Agent - request to store system information
→ Routed to Memory Agent

Request: "What's the best architecture pattern for microservices?"
🧠 Claude's routing decision: Claude - architectural advice and technical guidance
→ Claude handles it directly
```

### Demo 4: Multi-Agent Collaboration

Complex task: "Calculate the area of a circle with radius 10, store the formula in memory, and explain why pi is important"

```
📋 Workflow Plan:
1. Calculator: Calculate area using A = πr²
2. Memory: Store the formula "A = πr²"
3. Analysis: Explain mathematical significance of pi
4. Claude: Synthesize results into coherent response
```

## Usage Examples

### Basic Claude Agent

```python
from examples.claude_agent import ClaudeAgent
from a2a_server.message_broker import InMemoryMessageBroker
from a2a_server.models import Message, Part

# Create broker and agent
broker = InMemoryMessageBroker()
await broker.start()

claude = ClaudeAgent(message_broker=broker)
await claude.initialize(broker)

# Ask a question
msg = Message(parts=[Part(type="text", content="Explain async programming")])
response = await claude.process_message(msg)
print(response.parts[0].content)

await claude.close()
await broker.stop()
```

### Intelligent Router Pattern

```python
class IntelligentRouter(EnhancedAgent):
    def __init__(self, claude_agent: ClaudeAgent, message_broker=None):
        super().__init__(name="Intelligent Router", ...)
        self.claude = claude_agent

    async def process_message(self, message: Message) -> Message:
        # Ask Claude which agent should handle this
        routing_prompt = f"Route this request: {text}"
        decision = await self.claude.process_message(...)

        # Route based on Claude's decision
        if "Calculator" in decision:
            await self.send_message_to_agent("Calculator Agent", message)
        # ... etc
```

### Multi-Step Workflow Pattern

```python
class WorkflowAgent(EnhancedAgent):
    def __init__(self, claude_agent: ClaudeAgent, message_broker=None):
        super().__init__(name="Workflow Agent", ...)
        self.claude = claude_agent

    async def process_message(self, message: Message) -> Message:
        # Ask Claude to plan the workflow
        planning_prompt = f"Break down this task: {text}"
        plan = await self.claude.process_message(...)

        # Execute the planned steps
        # ...
```

## Configuration

### API Endpoint

Default: `http://localhost:4000/anthropic/v1/messages`

Change with:
```bash
python examples/claude_agent.py --api-url http://your-api:4000/anthropic/v1/messages
```

### API Key

Default: `xxx`

Change with:
```bash
python examples/claude_agent.py --api-key your-api-key
```

### Model

Default: `claude-3.5-sonnet`

Change with:
```bash
python examples/claude_agent.py --model claude-3-opus
```

## Architecture

```
┌─────────────────────────────────────────────────┐
│          Local Agent System                      │
│                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │Calculator│  │  Memory  │  │ Analysis │      │
│  │  Agent   │  │  Agent   │  │  Agent   │      │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘      │
│       │             │              │            │
│       └─────────────┼──────────────┘            │
│                     │                           │
│              ┌──────▼──────┐                    │
│              │   Message   │                    │
│              │   Broker    │                    │
│              └──────┬──────┘                    │
│                     │                           │
│              ┌──────▼──────┐                    │
│              │   Claude    │                    │
│              │   Agent     │                    │
│              └──────┬──────┘                    │
└─────────────────────┼────────────────────────────┘
                      │
                      │ HTTP/JSON
                      ▼
         ┌──────────────────────────┐
         │  Claude API (localhost)  │
         │  Port 4000               │
         └──────────────────────────┘
```

## Use Cases

### 1. Intelligent Task Routing

Use Claude's reasoning to route user requests to the appropriate specialist agent:

```python
router = IntelligentRouter(claude, broker)
response = await router.process_message(user_request)
# Claude analyzes the request and routes to best agent
```

### 2. Natural Language to Tool Execution

Convert natural language requests into tool calls:

```python
# User: "Calculate the compound interest on $1000 at 5% for 3 years"
# Claude: Routes to Calculator with parsed parameters
# Calculator: Performs calculation
# Claude: Explains the result in natural language
```

### 3. Multi-Step Problem Solving

Break complex tasks into agent-specific steps:

```python
# Task: "Analyze sales data, calculate trends, and store insights"
# Claude plans: Analysis → Calculator → Memory
# System executes the workflow automatically
```

### 4. Contextual Memory Management

Use Claude to decide what to remember:

```python
# Claude analyzes conversation and decides:
# - Important facts → Memory Agent
# - Calculations needed → Calculator Agent
# - Final synthesis → Claude's response
```

## Best Practices

### 1. System Prompts

Give Claude context about the agent system:

```python
system_prompt = """You are part of a multi-agent system.
Available agents: Calculator, Memory, Analysis.
Be concise and delegate when appropriate."""
```

### 2. Error Handling

Always handle API errors gracefully:

```python
try:
    response = await claude.call_claude(message)
except Exception as e:
    logger.error(f"Claude API error: {e}")
    # Fallback to default behavior
```

### 3. Rate Limiting

Add delays between requests if needed:

```python
await asyncio.sleep(0.5)  # Small delay between Claude calls
```

### 4. Token Management

Monitor token usage through events:

```python
# Claude publishes llm.response events with token counts
await claude.subscribe_to_agent_events(
    "Claude Agent",
    "llm.response",
    lambda e, d: print(f"Tokens used: {d['tokens']}")
)
```

## Testing

Run the test to verify integration:

```bash
# Start your LLM API on port 4000
# Then run:
python examples/claude_agent.py
```

Expected output shows Claude successfully:
- ✓ Answering questions
- ✓ Making routing decisions
- ✓ Coordinating with other agents
- ✓ Planning workflows

## Troubleshooting

### Connection Errors

```
Error: Failed to connect to http://localhost:4000
```

**Solution**: Make sure your LLM API is running:
```bash
# Check if API is responding
curl -k http://localhost:4000/anthropic/v1/messages \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer xxx" \
  -d '{"model": "claude-3.5-sonnet", "messages": [{"role": "user", "content": "test"}]}'
```

### API Key Issues

```
Error: Unauthorized
```

**Solution**: Update the API key:
```bash
python examples/claude_agent.py --api-key your-correct-key
```

### Model Not Found

```
Error: Model not found
```

**Solution**: Check available models and update:
```bash
python examples/claude_agent.py --model claude-3-opus
```

## Performance Tips

1. **Batch Similar Requests**: Group requests to same agent type
2. **Cache Common Responses**: Store frequently asked questions
3. **Use Async Properly**: Don't block on Claude calls
4. **Monitor Token Usage**: Track costs through event system

## Next Steps

- 🔧 Integrate with your specific workflow
- 📊 Add monitoring and metrics
- 🎯 Create custom routing logic
- 🔄 Implement conversation memory
- 🚀 Deploy with production LLM endpoint

## Summary

The Claude LLM Agent brings powerful natural language understanding and reasoning to your multi-agent system. It can:

✅ Answer complex questions
✅ Make intelligent routing decisions
✅ Coordinate multi-agent workflows
✅ Plan and execute multi-step tasks
✅ Provide natural language interfaces to specialized agents

Combined with the agent-to-agent messaging system, you now have a complete framework for building sophisticated AI applications! 🎉
