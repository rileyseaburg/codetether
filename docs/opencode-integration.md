# OpenCode Integration with A2A Server

This document describes how to integrate OpenCode (the AI coding agent) with the A2A Server to trigger agents from the web UI.

## Overview

The OpenCode integration allows you to:

1. **Register codebases** - Add projects that agents can work on
2. **Trigger agents remotely** - Start AI coding agents from the web UI
3. **Monitor progress** - Track agent status and view messages
4. **Manage sessions** - Interrupt, stop, or send follow-up messages
5. **Direct Chat** - Interact with agents without a specific project context using the "Global Codebase"

## Global Codebase & Direct Chat

CodeTether introduces the concept of a **Global Codebase** to enable workspace-less interactions.

- **Automatic Registration**: When an Agent Worker starts, it automatically registers a codebase named `global` pointing to the user's home directory (`~`).
- **Direct Chat UI**: The Dashboard features a "Chat Directly" button that immediately starts an OpenCode session on this global codebase.
- **Dynamic Models**: Available models are discovered dynamically from the worker (e.g., Gemini 3 Flash, Claude 3.5 Sonnet).
- **Model Filtering**: Workers automatically filter and register only models that have valid authentication in `auth.json`.

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    Web UI       │────▶│   A2A Server    │────▶│   OpenCode      │
│  (monitor.html) │     │  (FastAPI)      │     │   Server        │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                              │                        │
                              │                        │
                        ┌─────▼─────┐           ┌─────▼─────┐
                        │  OpenCode │           │  Target   │
                        │  Bridge   │           │ Codebase  │
                        └───────────┘           └───────────┘
```

## Installation

### 1. Build OpenCode from Local Fork

CodeTether includes a maintained fork of OpenCode in the `opencode/` directory. Build it from source:

```bash
# Navigate to the OpenCode directory
cd opencode

# Install dependencies and build
bun install
bun run build

# Link the binary globally (optional)
bun link
```

Alternatively, run OpenCode directly from the workspace:

```bash
# Run from the opencode directory
cd opencode && bun run dev
```

### 2. Verify OpenCode is available

```bash
which opencode
opencode --version
```

### 3. Install Python dependencies

```bash
pip install aiohttp
```

## Usage

### Starting the A2A Server

```bash
cd /path/to/A2A-Server-MCP
python -m a2a_server.server
```

The server will automatically detect and initialize the OpenCode bridge.

### Using the Web UI

1. Open the monitor UI at `http://localhost:8000/v1/monitor/`
2. Look for the **"🚀 OpenCode Agents"** panel on the left
3. Click **"➕ Register Codebase"** to add a project
4. Enter:
    - **Name**: Display name for the project
    - **Path**: Absolute path to the project directory
    - **Description**: Optional description
5. Click **"Register"**

### Triggering an Agent

1. Find your registered codebase in the panel
2. Click **"🎯 Trigger Agent"**
3. Enter a prompt describing what you want the agent to do
4. Select the agent type:
    - **Build**: Full access agent for development work
    - **Plan**: Read-only agent for analysis and planning
    - **General**: Multi-step task agent
    - **Explore**: Fast codebase search agent
5. Click **"🚀 Start Agent"**

### Agent Types

| Agent       | Description       | Use Case                              |
| ----------- | ----------------- | ------------------------------------- |
| **build**   | Full access agent | Writing code, making changes          |
| **plan**    | Read-only agent   | Code review, planning changes         |
| **general** | Task orchestrator | Complex multi-step tasks              |
| **explore** | Search specialist | Finding files, understanding codebase |

## API Reference

### Check Status

```
GET /v1/opencode/status
```

Returns OpenCode integration status.

### List Codebases

```
GET /v1/opencode/codebases
```

Returns all registered codebases.

### Register Codebase

```
POST /v1/opencode/codebases
Content-Type: application/json

{
  "name": "My Project",
  "path": "/home/user/projects/myproject",
  "description": "Optional description"
}
```

### Trigger Agent

```
POST /v1/opencode/codebases/{codebase_id}/trigger
Content-Type: application/json

{
  "prompt": "Add error handling to the API routes",
  "agent": "build",
  "model": "anthropic/claude-3-sonnet",
  "files": ["src/api.py"]
}
```

### Send Message to Agent

```
POST /v1/opencode/codebases/{codebase_id}/message
Content-Type: application/json

{
  "message": "Also add logging",
  "agent": "build"
}
```

### Interrupt Agent

```
POST /v1/opencode/codebases/{codebase_id}/interrupt
```

### Stop Agent

```
POST /v1/opencode/codebases/{codebase_id}/stop
```

### Get Agent Status

```
GET /v1/opencode/codebases/{codebase_id}/status
```

### Unregister Codebase

```
DELETE /v1/opencode/codebases/{codebase_id}
```

## Configuration

### Environment Variables

| Variable                | Description                         | Default       |
| ----------------------- | ----------------------------------- | ------------- |
| `OPENCODE_BIN`          | Path to opencode binary             | Auto-detected |
| `OPENCODE_DEFAULT_PORT` | Starting port for OpenCode servers  | 9777          |
| `OPENCODE_AUTO_START`   | Auto-start OpenCode when triggering | true          |

### OpenCode Configuration

You can customize OpenCode behavior by creating an `opencode.json` in your codebase directory:

```json
{
    "model": "anthropic/claude-3-sonnet",
    "agent": {
        "build": {
            "permission": {
                "edit": "allow",
                "bash": {
                    "*": "ask"
                }
            }
        }
    }
}
```

## Troubleshooting

### OpenCode not detected

If the bridge shows "OpenCode bridge not available":

1. Verify OpenCode is built from the local fork: `which opencode`
2. Rebuild if needed: `cd opencode && bun install && bun run build`
3. Add the binary path to your PATH or set `OPENCODE_BIN` environment variable
4. Restart the A2A server

### Agent not starting

Check the A2A server logs for errors. Common issues:

- Port already in use (try a different `OPENCODE_DEFAULT_PORT`)
- Insufficient permissions on the codebase directory
- OpenCode configuration errors

### Agent not responding

1. Check the agent status in the UI
2. Try interrupting and restarting the agent
3. Check OpenCode logs in the terminal

## Example Workflows

### Code Review

1. Register your project
2. Trigger the **plan** agent with: "Review the authentication implementation and suggest improvements"
3. Read the agent's analysis
4. Send follow-up questions

### Feature Implementation

1. Register your project
2. Trigger the **build** agent with: "Add user authentication with JWT tokens"
3. Monitor progress in the UI
4. Review changes when complete

### Codebase Exploration

1. Register an unfamiliar project
2. Trigger the **explore** agent with: "Find all API endpoints and explain the routing structure"
3. Get a quick overview of the codebase

## Ralph: Autonomous Development Loop

Ralph is CodeTether's fully autonomous development agent that implements entire PRDs (Product Requirements Documents) with zero human intervention.

### How Ralph Works

1. **PRD Input**: Define your project requirements as user stories with acceptance criteria
2. **Fresh Context Per Story**: Each user story spawns a new OpenCode instance for optimal context
3. **Iterative Implementation**: Ralph implements each story, runs acceptance tests, and commits
4. **Self-Healing**: If tests fail, Ralph re-analyzes using `progress.txt` context and retries
5. **Git Integration**: Atomic commits per user story with meaningful commit messages

### Ralph Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Ralph Loop                                │
│                                                                  │
│  PRD (YAML) ──▶ User Stories ──▶ For Each Story:                │
│                                    │                             │
│                                    ▼                             │
│                              ┌───────────┐                       │
│                              │ Spawn new │                       │
│                              │ OpenCode  │                       │
│                              └─────┬─────┘                       │
│                                    │                             │
│                                    ▼                             │
│                              ┌───────────┐                       │
│                              │ Implement │                       │
│                              │   Story   │                       │
│                              └─────┬─────┘                       │
│                                    │                             │
│                                    ▼                             │
│                              ┌───────────┐     ┌───────────┐    │
│                              │   Check   │────▶│  Update   │    │
│                              │ Criteria  │ Fail│progress.txt│   │
│                              └─────┬─────┘     └─────┬─────┘    │
│                                    │ Pass           │           │
│                                    ▼                │           │
│                              ┌───────────┐          │           │
│                              │  Commit   │◀─────────┘           │
│                              │  Changes  │                       │
│                              └─────┬─────┘                       │
│                                    │                             │
│                                    ▼                             │
│                              Next Story                          │
└─────────────────────────────────────────────────────────────────┘
```

### PRD Format (YAML)

```yaml
project: MyApp
branchName: ralph/new-feature
description: Add a new feature to the application
userStories:
  - id: US-001
    title: Add database migration
    description: As a developer, I need to add a new column to the database
    acceptanceCriteria:
      - Migration file exists in migrations/
      - Migration is reversible (has down migration)
      - Column is of correct type
  - id: US-002
    title: Update API endpoint
    description: As a user, I need the API to return the new field
    acceptanceCriteria:
      - GET /api/items returns new field
      - Field is properly validated
      - API docs are updated
```

### Ralph Dashboard

Access Ralph at `/dashboard/ralph`:

- **PRD Builder**: Interactive editor with YAML import/export
- **Live Execution**: Real-time logs showing implementation progress
- **Story Status**: Track pending/running/passed/failed stories
- **Agent Overview**: See which agents are working on which stories
- **Branch Management**: Auto-generated feature branches

### RLM Integration

Ralph leverages RLM (Recursive Language Models) for large codebase analysis:

- When context exceeds threshold (default: 80K tokens), RLM triggers automatically
- Subcalls analyze complex files without hitting context limits
- Progress context preserved across iterations

### Configuration

```bash
# Enable Ralph in dashboard
RALPH_ENABLED=1

# RLM settings for Ralph
export A2A_RLM_DEFAULT_SUBCALL_MODEL_REF="zai:glm-4.7"
export OPENCODE_RLM_ENABLED=1
```

### Example Workflow

1. **Navigate to `/dashboard/ralph`**
2. **Create or import a PRD** with user stories
3. **Click "Start Ralph"** - Ralph begins autonomous implementation
4. **Monitor progress** in the live log view
5. **Review commits** when all stories pass

---

## RLM (Recursive Language Models)

CodeTether supports RLM, allowing agents to process arbitrarily long contexts through recursive LLM calls in a Python REPL.

### How RLM Works

When an agent encounters a context that exceeds normal limits, it can use the RLM tool to:

1. Load context into a Python variable
2. Write Python code to analyze it programmatically
3. Make recursive sub-LLM calls via `llm_query()`
4. Return final output with `FINAL()` or `FINAL_VAR()`

### RLM Configuration

```bash
# Model resolution for subcalls
export A2A_RLM_DEFAULT_SUBCALL_MODEL_REF="zai:glm-4.7"
export A2A_RLM_FALLBACK_CHAIN="zai:glm-4.7,openai:gpt-4o-mini,controller"
export A2A_RLM_ALLOW_CONTROLLER_FALLBACK=1

# Guardrails
export A2A_RLM_MAX_SUBCALLS_PER_ITERATION=5
export A2A_RLM_MAX_TOTAL_SUBCALLS=100
export A2A_RLM_MAX_SUBCALL_TOKENS=8000
export A2A_RLM_MAX_ITERATIONS=20

# Enable on worker
export OPENCODE_RLM_ENABLED=1
```

### RLM Python API

In the RLM REPL, agents have access to:

```python
# Context is pre-loaded
print(f"Context length: {len(context)}")

# Query the LLM recursively
answer = llm_query("Summarize the main issues")
print(answer)

# Use Python for complex analysis
import re
matches = re.findall(r"TODO.*", context)
print(f"Found {len(matches)} TODOs")

# Return final output
FINAL("Here is my final answer")
# Or return a variable
FINAL_VAR(result)
```

### Model Resolution

RLM uses a priority-based model resolution for subcalls:

1. **Task override** - `subcall_model_ref` in task definition
2. **Server config** - `A2A_RLM_DEFAULT_SUBCALL_MODEL_REF` env var
3. **Fallback chain** - `A2A_RLM_FALLBACK_CHAIN` (comma-separated)
4. **Controller fallback** - Use same model as main controller (if allowed)

### Use Cases

- **Large codebase review** - Analyze monorepos without context limits
- **Multi-file refactoring** - Coordinate changes across many files
- **Security audits** - Systematically check for vulnerabilities at scale
- **Documentation generation** - Extract and synthesize information from many files

## Security Considerations

- **Path validation**: Only absolute paths within your filesystem are allowed
- **Process isolation**: Each codebase runs its own OpenCode server
- **Permission model**: OpenCode's permission system controls what agents can do
- **No remote access by default**: The A2A server only listens locally
- **RLM sandboxing**: Python REPL has network disabled by default

## Contributing

To extend the OpenCode integration:

1. **Bridge module**: `a2a_server/opencode_bridge.py`
2. **API endpoints**: `a2a_server/monitor_api.py` (opencode_router)
3. **UI components**: `ui/monitor.html` and `ui/monitor.js`

## License

This integration follows the same license as the A2A Server project.
