# Marketing Coordinator Agent

The Marketing Coordinator Agent orchestrates marketing initiatives by planning strategies and creating tasks for worker agents to execute.

## Overview

The Marketing Coordinator is a specialized agent that:
- **Plans marketing initiatives** using AI (Claude Opus 4.5 via Azure AI Foundry)
- **Creates tasks** for workers to execute marketing operations
- **Manages initiative lifecycle**: draft → planning → executing → monitoring
- **Coordinates across** creative, campaigns, automations, audiences, and analytics

## Architecture

```
Marketing Coordinator (Planner)
    ↓ (Creates Tasks)
A2A Task Queue
    ↓ (Workers Pick Up)
Worker Agents
    ↓ (MCP Tools Call)
Marketing APIs (Creative, Campaigns, Analytics, etc.)
```

## Task-Based Orchestration

The coordinator uses a task-based architecture for distributed execution:

1. **Coordinator receives request** → "Launch Q1 email campaign"
2. **Plans initiative** → Creates 5 tasks (design, copy, list building, automation, analytics)
3. **Workers pick up tasks** → Each task handled by specialized worker
4. **MCP tools execute** → Workers call marketing APIs via MCP
5. **Coordinator monitors** → Tracks task completion and initiative progress

## Installation

### From Source

```bash
cd agents/marketing_coordinator
pip install -r requirements.txt
```

### Running the Coordinator

```bash
python agent.py --model claude-opus
```

## Configuration

Environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `AZURE_OPENAI_ENDPOINT` | Azure AI Foundry endpoint | - |
| `AZURE_OPENAI_API_KEY` | Azure API key | - |
| `AZURE_DEPLOYMENT_NAME` | Model deployment name | `claude-opus-4.5` |
| `A2A_SERVER_URL` | A2A server URL | `http://localhost:8000` |

## Initiative Management

### Create Initiative

```python
from agents.marketing_coordinator import create_initiative

initiative = await create_initiative(
    title="Q1 Email Campaign",
    description="Launch Q1 promotional email campaign to existing customers",
    budget=10000,
    status="draft"
)
```

### Plan Tasks for Initiative

```python
from agents.marketing_coordinator import plan_initiative_tasks

tasks = await plan_initiative_tasks(
    initiative_id=initiative.id,
    a2a_server_url="http://localhost:8000"
)

# Creates tasks like:
# - "Design email creative"
# - "Write email copy"
# - "Build customer audience"
# - "Set up automation"
# - "Configure analytics tracking"
```

## Supported Marketing Skills

### Creative Generation
- Generate ad creatives from copy
- Batch generate multiple creatives
- Analyze creative performance
- Get top-performing creatives

### Campaigns
- Create marketing campaigns
- Update campaign status and budget
- Get campaign metrics
- List all campaigns

### Automations
- Create marketing automations
- Trigger automations manually
- List automations
- Update automation status

### Audiences
- Create geo-based audiences
- Create lookalike audiences
- Create custom audiences
- Get targeting data (zip codes, etc.)

### Analytics
- Get unified metrics across channels
- Calculate ROI metrics
- Analyze channel performance
- Thompson sampling for budget allocation
- Get conversion attribution

## MCP Tool Integration

The coordinator exposes 27 marketing MCP tools for agents to use:

```python
# Example: Generate creative
{
    "name": "generate_creative",
    "description": "Generate ad creative from winning copy using Gemini Imagen",
    "params": {
        "concept": "Product launch",
        "brand_guidelines": "Bold, modern, tech-focused"
    }
}

# Example: Create campaign
{
    "name": "create_campaign",
    "description": "Create a new marketing campaign",
    "params": {
        "name": "Q1 Promotion",
        "budget": 5000,
        "channels": ["email", "facebook", "tiktok"]
    }
}
```

## Worker Task Execution

Workers execute tasks created by the coordinator:

```python
# Worker picks up task
task = await get_next_task()

# Execute using MCP tools
if task.type == "generate_creative":
    result = await call_mcp_tool(
        "generate_creative",
        task.params
    )

# Mark complete
await complete_task(task.id, result)
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/marketing/initiatives` | POST | Create marketing initiative |
| `/v1/marketing/initiatives/{id}` | GET | Get initiative details |
| `/v1/marketing/initiatives/{id}/plan` | POST | Generate task plan for initiative |
| `/v1/marketing/initiatives/{id}/status` | PUT | Update initiative status |
| `/v1/marketing/initiatives` | GET | List all initiatives |

## Example Workflow

### Launch a Campaign

```bash
# 1. Create initiative
curl -X POST http://localhost:8000/v1/marketing/initiatives \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Q1 Product Launch",
    "description": "Launch new product with multi-channel campaign",
    "budget": 25000
  }'

# 2. Plan tasks (coordinator creates worker tasks)
curl -X POST http://localhost:8000/v1/marketing/initiatives/123/plan

# 3. Workers pick up and execute tasks automatically
# Monitor progress:
curl http://localhost:8000/v1/marketing/initiatives/123
```

## Troubleshooting

### Tasks not being created?

Check coordinator logs:
```bash
kubectl logs deployment/marketing-coordinator | grep "task"
```

### Workers not picking up tasks?

Verify worker connection:
```bash
curl http://localhost:8000/v1/workers
```

### Initiative stuck in "draft"?

Manually trigger planning:
```bash
curl -X POST http://localhost:8000/v1/marketing/initiatives/123/plan
```

## See Also

- [Marketing Tools](marketing-tools.md)
- [Distributed Workers](distributed-workers.md)
- [Agent Worker](agent-worker.md)
