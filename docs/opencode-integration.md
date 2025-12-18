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

| Agent | Description | Use Case |
|-------|-------------|----------|
| **build** | Full access agent | Writing code, making changes |
| **plan** | Read-only agent | Code review, planning changes |
| **general** | Task orchestrator | Complex multi-step tasks |
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

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENCODE_BIN` | Path to opencode binary | Auto-detected |
| `OPENCODE_DEFAULT_PORT` | Starting port for OpenCode servers | 9777 |
| `OPENCODE_AUTO_START` | Auto-start OpenCode when triggering | true |

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

## Security Considerations

- **Path validation**: Only absolute paths within your filesystem are allowed
- **Process isolation**: Each codebase runs its own OpenCode server
- **Permission model**: OpenCode's permission system controls what agents can do
- **No remote access by default**: The A2A server only listens locally

## Contributing

To extend the OpenCode integration:

1. **Bridge module**: `a2a_server/opencode_bridge.py`
2. **API endpoints**: `a2a_server/monitor_api.py` (opencode_router)
3. **UI components**: `ui/monitor.html` and `ui/monitor.js`

## License

This integration follows the same license as the A2A Server project.
