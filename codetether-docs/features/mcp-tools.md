---
title: MCP Tools
description: Model Context Protocol tool integration for AI agents
---

# MCP Tools

CodeTether includes a comprehensive MCP (Model Context Protocol) server that exposes all platform capabilities as tools that AI models can use directly.

## Overview

The MCP HTTP server (port 9000) provides **29 tools** covering:

- **Task Management** - Create, list, cancel tasks
- **Agent Discovery** - Find and communicate with agents
- **Codebase Operations** - Manage codebases and sessions
- **Ralph Integration** - Create and monitor autonomous development runs
- **PRD Chat** - AI-assisted PRD generation

## Configuration

```bash
export MCP_HTTP_ENABLED=true
export MCP_HTTP_PORT=9000
```

## Quick Start

```bash
# List available tools
curl -s http://localhost:9000/mcp/v1/rpc \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}'
```

---

## Ralph MCP Tools

The most powerful MCP tools enable **end-to-end autonomous development** - from PRD creation to implementation.

### ralph_create_run

Create a new Ralph run to implement a PRD autonomously.

```bash
curl -s -X POST http://localhost:9000/mcp/v1/rpc \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "ralph_create_run",
      "arguments": {
        "project": "My Feature",
        "branch_name": "feature/my-feature",
        "description": "Implement user authentication",
        "codebase_id": "ec77c942",
        "user_stories": [
          {
            "id": "US-001",
            "title": "Add login endpoint",
            "description": "As a user, I can login with email and password",
            "acceptance_criteria": [
              "POST /api/auth/login accepts email and password",
              "Returns JWT token on success",
              "Returns 401 on invalid credentials"
            ]
          }
        ],
        "max_iterations": 5
      }
    }
  }'
```

**Response:**
```json
{
  "success": true,
  "run_id": "ad564688-d272-4907-ac59-8acc20a584d5",
  "status": "pending",
  "current_iteration": 0,
  "max_iterations": 5,
  "message": "Ralph run started for project \"My Feature\""
}
```

!!! warning "Codebase ID Required"
    Tasks without a `codebase_id` won't be picked up by workers. Always specify which codebase to run in.

### ralph_get_run

Monitor the status of a Ralph run.

```bash
curl -s -X POST http://localhost:9000/mcp/v1/rpc \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "ralph_get_run",
      "arguments": {
        "run_id": "ad564688-d272-4907-ac59-8acc20a584d5"
      }
    }
  }'
```

**Response:**
```json
{
  "run_id": "ad564688-d272-4907-ac59-8acc20a584d5",
  "status": "completed",
  "current_iteration": 2,
  "max_iterations": 5,
  "story_results": [
    {
      "story_id": "US-001",
      "status": "passed",
      "result": "Story implemented successfully..."
    }
  ]
}
```

### ralph_list_runs

List all Ralph runs, optionally filtered by codebase.

```bash
curl -s -X POST http://localhost:9000/mcp/v1/rpc \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "ralph_list_runs",
      "arguments": {
        "codebase_id": "ec77c942",
        "limit": 10
      }
    }
  }'
```

### ralph_cancel_run

Cancel a running Ralph execution.

```bash
curl -s -X POST http://localhost:9000/mcp/v1/rpc \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "ralph_cancel_run",
      "arguments": {
        "run_id": "ad564688-d272-4907-ac59-8acc20a584d5"
      }
    }
  }'
```

---

## PRD Chat Tools

AI-assisted PRD generation through conversational interface.

### prd_chat

Send a message to the AI PRD assistant to collaboratively build a PRD.

```bash
curl -s -X POST http://localhost:9000/mcp/v1/rpc \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "prd_chat",
      "arguments": {
        "message": "I want to build a TODO list feature with add, complete, and delete tasks",
        "conversation_id": "my-prd-session"
      }
    }
  }'
```

### prd_list_sessions

List PRD chat sessions for a codebase.

```bash
curl -s -X POST http://localhost:9000/mcp/v1/rpc \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "prd_list_sessions",
      "arguments": {
        "codebase_id": "ec77c942"
      }
    }
  }'
```

---

## End-to-End Example

Here's a complete workflow from MCP to Ralph to successful implementation:

### 1. Set Active Codebase

```bash
curl -s -X POST http://localhost:9000/mcp/v1/rpc \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "set_active_codebase",
      "arguments": {
        "codebase_id": "ec77c942"
      }
    }
  }'
```

### 2. Create Ralph Run

```bash
curl -s -X POST http://localhost:9000/mcp/v1/rpc \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "ralph_create_run",
      "arguments": {
        "project": "MCP E2E Test",
        "branch_name": "feature/mcp-e2e-test",
        "description": "Test MCP to Ralph integration",
        "codebase_id": "ec77c942",
        "user_stories": [
          {
            "id": "US-001",
            "title": "Create test file",
            "description": "Create a test file to verify integration",
            "acceptance_criteria": [
              "File test_mcp_e2e.txt exists in project root",
              "File contains text: MCP E2E Test Successful"
            ]
          }
        ],
        "max_iterations": 3
      }
    }
  }'
```

### 3. Monitor Progress

```bash
# Poll until complete
RUN_ID="your-run-id"
while true; do
  STATUS=$(curl -s -X POST http://localhost:9000/mcp/v1/rpc \
    -H "Content-Type: application/json" \
    -d "{\"jsonrpc\": \"2.0\", \"id\": 1, \"method\": \"tools/call\", \"params\": {\"name\": \"ralph_get_run\", \"arguments\": {\"run_id\": \"$RUN_ID\"}}}" \
    | jq -r '.result.status')
  
  echo "Status: $STATUS"
  
  if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
    break
  fi
  sleep 5
done
```

### 4. Verify Success

```bash
# Check the file was created
cat test_mcp_e2e.txt
# Output: MCP E2E Test Successful
```

---

## Task Management Tools

### create_task

Create a task for worker execution.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `title` | string | Yes | Task title |
| `description` | string | No | Detailed description |
| `codebase_id` | string | No | Target codebase |
| `agent_type` | string | No | `build`, `plan`, `general`, `explore` |
| `priority` | integer | No | Higher = more urgent |

### get_task

Get task status by ID.

### list_tasks

List tasks with optional status filter.

### cancel_task

Cancel a pending or running task.

---

## Agent Discovery Tools

### discover_agents

List all registered worker agents.

### get_agent

Get details about a specific agent.

### register_agent

Register as a worker agent.

---

## Codebase Tools

### list_codebases

List all registered codebases.

### set_active_codebase

Set the default codebase for subsequent operations.

### get_current_codebase

Get the currently active codebase.

---

## All Available Tools

| Tool | Category | Description |
|------|----------|-------------|
| `send_message` | Messaging | Send message to agent |
| `send_message_async` | Messaging | Async message (returns task_id) |
| `send_to_agent` | Messaging | Send to specific named agent |
| `get_messages` | Messaging | Get conversation history |
| `create_task` | Tasks | Create new task |
| `get_task` | Tasks | Get task status |
| `list_tasks` | Tasks | List all tasks |
| `cancel_task` | Tasks | Cancel a task |
| `get_task_updates` | Tasks | Poll for task changes |
| `discover_agents` | Agents | List registered agents |
| `get_agent` | Agents | Get agent details |
| `register_agent` | Agents | Register as worker |
| `refresh_agent_heartbeat` | Agents | Keep agent visible |
| `get_agent_card` | Agents | Get server's agent card |
| `list_codebases` | Codebases | List all codebases |
| `set_active_codebase` | Codebases | Set default codebase |
| `get_current_codebase` | Codebases | Get active codebase |
| `search_tools` | Discovery | Search available tools |
| `get_tool_schema` | Discovery | Get tool parameter schema |
| `ralph_create_run` | Ralph | Start autonomous development |
| `ralph_get_run` | Ralph | Get run status |
| `ralph_list_runs` | Ralph | List all runs |
| `ralph_cancel_run` | Ralph | Cancel a run |
| `prd_chat` | PRD | AI-assisted PRD chat |
| `prd_list_sessions` | PRD | List chat sessions |

---

## Integration with AI Assistants

MCP tools can be used by any AI assistant that supports tool calling:

### Claude (via MCP)

```json
{
  "mcpServers": {
    "codetether": {
      "command": "curl",
      "args": ["-s", "http://localhost:9000/mcp/v1/rpc"],
      "transport": "http"
    }
  }
}
```

### CodeTether

CodeTether can use MCP tools directly for autonomous development workflows.

### Custom Integrations

Any system that can make HTTP POST requests to the MCP endpoint can use these tools.

---

## Next Steps

- [Ralph Guide](ralph.md) - Deep dive into autonomous development
- [Agent Worker](agent-worker.md) - Deploy workers to execute tasks
- [CodeTether Integration](agent.md) - AI coding capabilities
