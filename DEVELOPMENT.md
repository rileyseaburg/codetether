# CodeTether

[![Apache License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-supported-blue.svg)](https://www.docker.com/)
[![Kubernetes](https://img.shields.io/badge/kubernetes-ready-blue.svg)](https://kubernetes.io/)

**CodeTether is a production-ready Agent-to-Agent (A2A) platform with Model Context Protocol (MCP) integration for building and orchestrating AI agent systems.**

CodeTether provides a complete A2A protocol server that bridges the gap between AI agents and external tools through MCP integration. The platform enables agents to communicate using the standardized A2A protocol while accessing a rich ecosystem of tools via the Model Context Protocol.

## Key Features

- **🔗 Full A2A Protocol Support**: Complete implementation of Agent-to-Agent communication standard
- **🛠️ MCP Tool Integration**: Access external tools and resources through Model Context Protocol
- **🤖 LLM Integration**: Connect Claude or other LLMs for intelligent agent coordination
- **💻 CodeTether Integration**: Trigger AI coding agents from the web UI on registered codebases
- **📡 Real-time Communication**: Server-Sent Events (SSE) for streaming responses
- **💬 Agent-to-Agent Messaging**: Publish/subscribe and direct messaging between agents
- **👁️ Real-time Monitor UI**: Web-based dashboard for agent supervision and human intervention
- **📱 Swift Liquid Glass UI**: Native iOS/macOS app with Apple-style glassmorphism design
- **🔄 Distributed Workers**: Remote agent workers with task queues and watch mode
- **📂 Runtime Session Access**: Immediate access to local CodeTether sessions without registration
- **📜 Session History**: Browse and resume past CodeTether sessions from any device
- **⏯️ Session Resumption**: Continue conversations with AI agents from where you left off
- **� Model Filtering**: Workers automatically filter and register only authenticated models from `auth.json`
- **�📊 Real-time Output Streaming**: See agent responses as they happen via SSE
- **🔐 Keycloak Authentication**: Enterprise SSO with OAuth2/OIDC via Keycloak
- **🚀 Production Ready**: Kubernetes deployment with Helm charts
- **🔐 Enterprise Security**: Authentication, authorization, and network policies
- **📊 Observability**: Built-in monitoring, health checks, and metrics
- **⚡ Scalable**: Redis-based message broker with horizontal scaling
- **🐳 Container Native**: Docker and Kubernetes optimized

## Quick Start

### 🛠️ Local Development (Recommended for Getting Started)

**Start the full environment (Python + Next.js + Worker)**
```bash
# Install all dependencies
make install-dev

# Run Python server, Next.js marketing site, and Agent Worker together
make dev
```

**Terminal 1: Run the CodeTether Server (Python only)**
```bash
# Install dependencies
pip install -r requirements.txt

# Run the server with enhanced agents
python run_server.py run --name "CodeTether Server" --port 8000

# The server will start with:
# - Calculator Agent (math operations)
# - Analysis Agent (text analysis, weather)
# - Memory Agent (data storage)
# - Media Agent (LiveKit sessions)
```

**Terminal 2: Run the Agent Worker**
```bash
# One-command deploy (registers current directory as a codebase)
./deploy-worker.sh --server http://localhost:8000 --codebases .

# Or run the binary directly:
codetether worker --server http://localhost:8000 --codebases . --auto-approve safe --name "Local Worker"

# Or via make:
make worker
```

**Terminal 3: Run Agent-to-Agent Messaging Demo**
```bash
# Run the comprehensive agent messaging demo
python examples/agent_to_agent_messaging.py

# This demonstrates:
# - Direct agent-to-agent messaging
# - Event publishing and subscribing
# - Multi-agent coordination
# - Data aggregation across agents
```

**Terminal 4: Connect with Claude LLM**
```bash
# Run Claude integration demo (requires Claude API on localhost:4000)
python examples/claude_agent.py

# Or connect to a remote CodeTether server
python examples/connect_remote_agent.py --url http://localhost:8000 --interactive
```

**Test the Server**
```bash
# Get the agent card
curl http://localhost:8000/.well-known/agent-card.json

# Send a message using JSON-RPC 2.0
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "message/send",
    "params": {
      "message": {
        "parts": [{"type": "text", "content": "Calculate 25 * 4"}]
      }
    }
  }'
```

### � Direct Chat & Global Codebase

CodeTether now supports **Direct Chat**, allowing you to interact with AI agents without needing to register a specific project codebase.

- **Global Codebase**: When a worker starts, it automatically registers a "global" codebase pointing to the user's home directory (`~`).
- **Workspace-less Interaction**: Use the "Chat Directly" button in the Dashboard to start a session that isn't tied to a specific project.
- **Dynamic Model Discovery**: Workers automatically report available models (e.g., Gemini 3 Flash, Claude 3.5 Sonnet) to the server, which are then available in the UI.

### �🐳 Docker Deployment

The fastest way to get started with Docker:

```bash
# Build the Docker image
docker build -t codetether:latest .

# Run with default configuration
docker run -p 8000:8000 codetether:latest

# Test the server
curl http://localhost:8000/.well-known/agent-card.json
```

**Connecting to Host VM's CodeTether:**

When running the A2A server in Docker, you can connect to CodeTether running on your host machine:

```bash
# Docker Desktop (Mac/Windows) - uses host.docker.internal automatically
docker run -p 8000:8000 \
  -e OPENCODE_HOST=host.docker.internal \
  -e OPENCODE_PORT=9777 \
  codetether:latest

# Linux - add host.docker.internal or use host IP
docker run -p 8000:8000 \
  --add-host=host.docker.internal:host-gateway \
  -e OPENCODE_HOST=host.docker.internal \
  -e OPENCODE_PORT=9777 \
  codetether:latest

# Alternative: use your host's actual IP address
docker run -p 8000:8000 \
  -e OPENCODE_HOST=192.168.1.100 \
  -e OPENCODE_PORT=9777 \
  codetether:latest
```

This allows the containerized A2A server to access CodeTether sessions from the host VM via the CodeTether HTTP API.

### ☸️ Kubernetes Deployment (Production)

Deploy to Kubernetes using the included Helm chart. For complete OCI registry deployment and external agent synchronization, see **[HELM_OCI_DEPLOYMENT.md](HELM_OCI_DEPLOYMENT.md)**.

**Quick Install (Local Chart):**

```bash
# Build and tag the image for your registry
docker build -t your-registry/codetether:latest .
docker push your-registry/codetether:latest

# Install with Helm
helm upgrade --install a2a-server ./chart/a2a-server \
  --set image.repository=your-registry/a2a-server \
  --set image.tag=latest \
  --namespace a2a-system --create-namespace
```

**OCI Registry Deployment (Recommended):**

**Quantum Forge Registry (One-Command Deploy):**
```powershell
# Windows - Deploy everything (Docker + Helm)
.\deploy-to-quantum-forge.ps1 -Version "v1.0.0"

# Linux/Mac
./deploy-to-quantum-forge.sh
```

**Manual OCI Deployment:**
```bash
# Push chart to OCI registry (e.g., GitHub Container Registry)
helm package chart/a2a-server
helm push a2a-server-0.1.0.tgz oci://ghcr.io/rileyseaburg/charts

# Or to Quantum Forge
helm push a2a-server-0.1.0.tgz oci://registry.quantum-forge.net/library

# Install from OCI registry
helm install a2a-server oci://registry.quantum-forge.net/library/a2a-server \
  --version 0.1.0 \
  --namespace a2a-system \
  --create-namespace
```

**Enable MCP for Agent Synchronization:**

The deployment includes an MCP HTTP server (port 9000) that allows external agents to connect and synchronize:

```bash
# Test the MCP endpoint
kubectl port-forward -n a2a-system svc/a2a-server 9000:9000
curl http://localhost:9000/mcp/v1/tools

# Or use the test script
./test-mcp-server.ps1  # Windows
./test-mcp-server.sh   # Linux/Mac
```

**Configure Cline/Claude Dev to Connect:**

Add to your `cline_mcp_settings.json` (see `examples/cline_mcp_config_example.json`):

```json
{
  "mcpServers": {
    "a2a-server-production": {
      "command": "python",
      "args": [
        "examples/mcp_external_client.py",
        "--endpoint",
        "http://a2a.example.com:9000/mcp/v1/rpc"
      ],
      "disabled": false,
      "autoApprove": ["calculator", "text_analyzer"]
    }
  }
}
```

**Full Documentation:**
- � [Quantum Forge Deployment](QUANTUM_FORGE_DEPLOYMENT.md) - One-command deploy to Quantum Forge registry
- �📘 [Helm OCI Deployment Guide](HELM_OCI_DEPLOYMENT.md) - Complete guide for OCI registry deployment
- 📘 [Distributed A2A Guide](DISTRIBUTED_A2A_GUIDE.md) - Multi-agent coordination
- 📘 [Chart Configuration](chart/README.md) - Helm chart values and examples

## Architecture

### Core Components

- **Enhanced CodeTether**: Extended A2A protocol implementation with MCP integration
- **MCP Client**: Interface for communicating with external MCP servers
- **Task Manager**: Handles complex task lifecycles and state management
- **Message Broker**: Redis-based pub/sub for agent coordination and messaging
- **LiveKit Bridge**: Real-time audio/video communication support
- **Agent-to-Agent Messaging**: Direct communication between agents with pub/sub patterns

### MCP Integration

This server acts as an MCP client, allowing A2A agents to access external tools and resources:

```python
# Example: Agent using MCP tools
from a2a_server.mcp_client import MCPClient

async def process_with_tools(message):
    # Access file system tools
    file_content = await mcp_client.call_tool("file_read", {"path": "/data/input.txt"})

    # Process with external service
    result = await mcp_client.call_tool("analyze_text", {"text": file_content})

    return result
```

### Agent-to-Agent Messaging

Agents can communicate directly with each other using the message broker:

#### Publishing Events

Agents can publish events that other agents can subscribe to:

```python
from a2a_server.enhanced_agents import EnhancedAgent
from a2a_server.models import Message, Part

class MyAgent(EnhancedAgent):
    async def process_message(self, message: Message) -> Message:
        # Perform some work
        result = await self.do_work(message)

        # Publish an event when done
        await self.publish_event("work.completed", {
            "result": result,
            "timestamp": datetime.utcnow().isoformat()
        })

        return Message(parts=[Part(type="text", content="Work completed!")])
```

#### Subscribing to Events

Agents can subscribe to events from other agents:

```python
class MonitorAgent(EnhancedAgent):
    async def initialize(self, message_broker=None):
        await super().initialize(message_broker)

        # Subscribe to events from another agent
        await self.subscribe_to_agent_events(
            "Calculator Agent",
            "calculation.complete",
            self.handle_calculation_result
        )

    async def handle_calculation_result(self, event_type: str, data: dict):
        print(f"Received calculation result: {data}")
```

#### Sending Direct Messages

Agents can send messages directly to specific agents:

```python
class CoordinatorAgent(EnhancedAgent):
    async def process_message(self, message: Message) -> Message:
        # Send work to calculator agent
        calc_message = Message(parts=[Part(type="text", content="Calculate 10 + 5")])
        await self.send_message_to_agent("Calculator Agent", calc_message)

        # Send work to analysis agent
        analysis_message = Message(parts=[Part(type="text", content="Analyze data")])
        await self.send_message_to_agent("Analysis Agent", analysis_message)

        return Message(parts=[Part(type="text", content="Tasks distributed")])
```

#### Complete Example

See `examples/agent_to_agent_messaging.py` for a complete demonstration of:
- Direct agent-to-agent messaging
- Event publishing and subscribing
- Multi-agent coordination patterns
- Data aggregation across agents

```bash
# Run the agent messaging demo
python examples/agent_to_agent_messaging.py
```

## Configuration

### Environment Variables

Create a `.env` file with your configuration:

```bash
# Server Configuration
A2A_HOST=0.0.0.0
A2A_PORT=8000
A2A_LOG_LEVEL=INFO

# Agent Configuration
A2A_AGENT_NAME=Enhanced A2A Agent
A2A_AGENT_DESCRIPTION=A2A agent with MCP tool integration
A2A_AGENT_ORG=Your Organization

# MCP Configuration
MCP_SERVER_URLS=http://localhost:3001,http://localhost:3002
MCP_TIMEOUT=30

# CodeTether Configuration
# Host where CodeTether API is running (for container->host communication)
# Use 'localhost' for local development
# Use 'host.docker.internal' for Docker Desktop (Mac/Windows)
# Use actual host IP for Docker on Linux
OPENCODE_HOST=localhost
OPENCODE_PORT=9777

# Redis Configuration (for message broker)
REDIS_URL=redis://localhost:6379/0
USE_REDIS=false  # Set to true to use Redis, false for in-memory broker

# Authentication (optional)
A2A_AUTH_ENABLED=false
A2A_AUTH_TOKENS=client1:secret123,client2:secret456
```

### Database Configuration

The A2A server requires PostgreSQL. **Development and production use separate databases** to ensure isolation.

| Environment | Database | Usage |
|-------------|----------|-------|
| Development | `a2a_server_dev` | Local `make dev`, testing |
| Production | `a2a_server` | Production deployment |

**Environment Variables:**
```bash
# Development (default in .env)
DATABASE_URL=postgresql://postgres:password@localhost:5432/a2a_server_dev

# Production
DATABASE_URL=postgresql://postgres:password@localhost:5432/a2a_server
```

**Running Migrations:**

```bash
# Run migrations on dev database
python scripts/migrate.py --dev

# Run migrations on prod database
python scripts/migrate.py --prod

# Create database if it doesn't exist, then migrate
python scripts/migrate.py --dev --create

# Use a specific database URL
python scripts/migrate.py --url postgresql://user:pass@host:5432/dbname
```

**Creating a New Database:**

```bash
# Create dev database and run migrations
python scripts/migrate.py --dev --create

# Or manually via psql
psql -U postgres -c "CREATE DATABASE a2a_server_dev;"
python scripts/migrate.py --dev
```

### Migration Catalog

All migrations live in `a2a_server/migrations/`. Apply them in order with `psql -f` or the migrate script.

| Migration | Purpose |
|-----------|---------|
| `003_create_users_table.sql` | Users table with concurrency limits |
| `004_hosted_workers.sql` | Worker registration and heartbeat tracking |
| `005_notification_reliability.sql` | Email notification delivery tracking |
| `006_stripe_tier_wiring.sql` | Stripe subscription tier columns on tenants |
| `007_agent_routing.sql` | Agent-targeted task routing (capabilities, deadlines) |
| `008_model_routing.sql` | Model preference routing for tasks |
| `009_k8s_tenant_columns.sql` | Per-tenant K8s namespace and URL columns |
| `010_task_runs_tenant_isolation.sql` | Tenant isolation + RLS on `task_runs` |
| `011_prd_chat_sessions.sql` | PRD-driven chat session storage |
| `012_analytics_events.sql` | First-party analytics event stream + attribution |
| `013_cronjobs.sql` | Scheduled job definitions and run history |
| `014_worker_profiles.sql` | Worker capability profiles and routing metadata |
| `015_proactive_rules.sql` | Proactive automation rule definitions |
| `016_proactive_personas.sql` | Agent persona configuration |
| `017_perpetual_loops.sql` | Long-running background task loop tracking |
| `018_audit_decisions.sql` | Audit decision records |
| `018_token_billing.sql` | Token-based billing (usage tracking, credits, budgets) |
| `019_finops.sql` | FinOps cost analysis and optimization |
| `020_marketing_automation.sql` | Marketing campaign orchestration |
| `021_conversion_tracking.sql` | Ad conversion tracking and attribution |
| `022_codebase_to_workspace.sql` | Rename codebases → workspaces |
| `023_okr.sql` | OKR tables (objectives, key results, runs) |
| `024_okr_rls.sql` | RLS policies for OKR tables + `get_current_tenant_id()` helper |
| `025_rbac_user_roles_rls.sql` | RBAC user role assignments with RLS |
| `enable_rls.sql` | Enable RLS on core tables (workers, workspaces, tasks, sessions) |
| `disable_rls.sql` | Rollback: disable all RLS policies |

### Database Schema Overview

The PostgreSQL schema is organized into these table groups:

**Core Platform:**

| Table | Description | Tenant-scoped |
|-------|-------------|---------------|
| `tenants` | Multi-tenant registry with Stripe + K8s metadata | No (root table) |
| `users` | User accounts with concurrency limits | Yes |
| `workers` | Registered worker instances | Yes |
| `workspaces` | Codebases/projects registered for agent work | Yes |
| `tasks` | Task definitions and status | Yes |
| `task_runs` | Task execution runs with lease-based claiming | Yes |
| `sessions` | Agent chat sessions | Yes |

**OKR (Objectives & Key Results):**

| Table | Description | Tenant-scoped |
|-------|-------------|---------------|
| `okrs` | Objective definitions with status workflow | Yes |
| `okr_key_results` | Measurable key results per OKR | Via FK to `okrs` |
| `okr_runs` | Execution runs per OKR | Via FK to `okrs` |

**Billing & Analytics:**

| Table | Description | Tenant-scoped |
|-------|-------------|---------------|
| `token_usage` | Per-request token consumption records | Yes |
| `tenant_credits` | Prepaid credit balances | Yes |
| `tenant_budgets` | Monthly spend caps | Yes |
| `analytics_events` | First-party event stream | Yes |
| `analytics_identity_map` | Anonymous → known user stitching | Yes |
| `cronjobs` / `cronjob_runs` | Scheduled jobs and run history | Yes |

### Row-Level Security (RLS)

PostgreSQL RLS provides **database-level tenant isolation** as a defense-in-depth layer on top of application-level `WHERE tenant_id = $1` filtering.

**How it works:**

1. The Python API sets a session variable before each query:
   ```python
   from .database import tenant_scope

   async with tenant_scope(tenant_id) as conn:
       rows = await conn.fetch('SELECT * FROM okrs')  # RLS filters automatically
   ```

2. This calls `SET app.current_tenant_id = '<tenant_id>'` on the PostgreSQL connection

3. RLS policies on each table enforce:
   - `SELECT/INSERT/UPDATE/DELETE` only allowed where `tenant_id = get_current_tenant_id()`
   - `NULL` tenant context (no session var set) allows access for backward compatibility
   - `a2a_admin` role bypasses all RLS for maintenance operations

4. Child tables without `tenant_id` (e.g., `okr_key_results`, `okr_runs`) inherit isolation through FK-based subquery policies:
   ```sql
   CREATE POLICY tenant_isolation_okr_kr_select ON okr_key_results
       FOR SELECT
       USING (EXISTS (
           SELECT 1 FROM okrs WHERE okrs.id = okr_key_results.okr_id
             AND okrs.tenant_id = get_current_tenant_id()
       ));
   ```

**Tables with RLS enabled:**

| Table | Policy Pattern | Migration |
|-------|---------------|----------|
| `workers` | Direct `tenant_id` match | `enable_rls.sql` |
| `workspaces` | Direct `tenant_id` match | `enable_rls.sql` |
| `tasks` | Direct `tenant_id` match | `enable_rls.sql` |
| `sessions` | Direct `tenant_id` match | `enable_rls.sql` |
| `task_runs` | Direct `tenant_id` match | `010_task_runs_tenant_isolation.sql` |
| `okrs` | Direct `tenant_id` match | `024_okr_rls.sql` |
| `okr_key_results` | FK subquery via `okrs` | `024_okr_rls.sql` |
| `okr_runs` | FK subquery via `okrs` | `024_okr_rls.sql` |
| `cronjobs` | Direct `tenant_id` match | `013_cronjobs.sql` |
| `cronjob_runs` | Direct `tenant_id` match | `013_cronjobs.sql` |
| `analytics_events` | Direct `tenant_id` match | `012_analytics_events.sql` |
| `analytics_identity_map` | Direct `tenant_id` match | `012_analytics_events.sql` |

**Environment variable:** `RLS_ENABLED=true` (default). Set to `false` to disable RLS context setting in the Python API (policies remain in PostgreSQL but `get_current_tenant_id()` returns NULL, allowing access).

**Checking RLS status:**
```sql
-- View which tables have RLS enabled
SELECT * FROM rls_status;

-- List all policies on a table
SELECT policyname, tablename FROM pg_policies WHERE tablename = 'okrs';
```

**Rollback:**
```bash
# Disable all RLS policies (core tables only)
psql -d a2a_server_dev -f a2a_server/migrations/disable_rls.sql
```

### Helm Chart Configuration

The Helm chart supports multiple deployment environments:

- **Development**: `chart/a2a-server/examples/values-dev.yaml`
- **Staging**: `chart/a2a-server/examples/values-staging.yaml`
- **Production**: `chart/a2a-server/examples/values-prod.yaml`

Key configuration options:
- Image repository and tag
- Resource limits and requests
- Autoscaling settings
- Redis configuration
- Security and network policies
- Monitoring and observability

## API Reference

### A2A Protocol Endpoints

The A2A server uses **JSON-RPC 2.0** over HTTP. All method calls are sent to the root endpoint (`/`) with the method specified in the JSON request body.

**Key Endpoints:**
- **`POST /`** - JSON-RPC 2.0 endpoint for all A2A protocol methods
- **`GET /.well-known/agent-card.json`** - Agent discovery card
- **`GET /agents`** - List all registered agents (when using message broker)
- **`GET /health`** - Health check endpoint
- **`POST /v1/livekit/token`** - Get LiveKit token for media sessions

### CodeTether Integration Endpoints

The server provides REST endpoints for CodeTether agent management:

**Codebases:**
- **`GET /v1/agent/codebases`** - List all registered codebases
- **`POST /v1/agent/codebases`** - Register a new codebase
- **`GET /v1/agent/codebases/{id}`** - Get codebase details
- **`DELETE /v1/agent/codebases/{id}`** - Unregister a codebase

**Tasks:**
- **`GET /v1/agent/tasks`** - List all tasks (filter by status, worker_id)
- **`POST /v1/agent/tasks`** - Create a new task
- **`GET /v1/agent/tasks/{id}`** - Get task details
- **`PUT /v1/agent/tasks/{id}/status`** - Update task status
- **`POST /v1/agent/tasks/{id}/output`** - Stream output to task (workers)
- **`GET /v1/agent/tasks/{id}/output`** - Get task output
- **`GET /v1/agent/tasks/{id}/output/stream`** - SSE stream for real-time output

**Sessions:**
- **`GET /v1/agent/codebases/{id}/sessions`** - List sessions for a codebase
- **`POST /v1/agent/codebases/{id}/sessions/sync`** - Sync sessions from worker
- **`POST /v1/agent/codebases/{id}/sessions/{session_id}/ingest`** - Ingest external chat/session transcripts (e.g., VS Code chat)
- **`GET /v1/agent/codebases/{id}/sessions/{session_id}/messages`** - Get session messages
- **`POST /v1/agent/codebases/{id}/sessions/{session_id}/resume`** - Resume a session

**Workers:**
- **`POST /v1/agent/workers/register`** - Register a worker
- **`POST /v1/agent/workers/{id}/unregister`** - Unregister a worker

### Runtime Sessions API

Direct access to local agent sessions without requiring codebase registration:

- **`GET /v1/agent/runtime/status`** - Check if agent runtime is available
- **`GET /v1/agent/runtime/projects`** - List all local projects
- **`GET /v1/agent/runtime/sessions`** - List all sessions (with pagination)
- **`GET /v1/agent/runtime/sessions/{id}`** - Get session details
- **`GET /v1/agent/runtime/sessions/{id}/messages`** - Get conversation history
- **`GET /v1/agent/runtime/sessions/{id}/parts`** - Get message content parts

```bash
# Check runtime status (shows session count immediately)
curl http://localhost:8000/v1/agent/runtime/status
# {"available": true, "projects": 3, "sessions": 247}

# List all sessions
curl http://localhost:8000/v1/agent/runtime/sessions?limit=10

# Get messages for a specific session
curl http://localhost:8000/v1/agent/runtime/sessions/{session_id}/messages
```

### Authentication Endpoints

When Keycloak is configured:

- **`POST /v1/auth/login`** - Authenticate with username/password
- **`POST /v1/auth/refresh`** - Refresh access token
- **`GET /v1/auth/userinfo`** - Get current user info
- **`POST /v1/auth/logout`** - Invalidate session

### A2A Protocol Methods

The server implements all core A2A protocol methods via JSON-RPC:

- **`message/send`**: Send a message and receive a synchronous response
- **`message/stream`**: Send a message with real-time streaming updates
- **`tasks/get`**: Retrieve information about running or completed tasks
- **`tasks/cancel`**: Cancel a running task
- **`tasks/resubscribe`**: Reconnect to a streaming task session

### Agent Discovery

Agents automatically register and can be discovered:

```bash
# Get agent card (shows available agents and their capabilities)
curl http://localhost:8000/.well-known/agent-card.json

# List all registered agents (when using message broker)
curl http://localhost:8000/agents
```

### Example Usage

#### Using the CLI Client

The CLI client handles JSON-RPC formatting automatically:

```bash
# Send a simple message
python examples/a2a_cli.py http://localhost:8000 --message "Calculate 10 + 5"

# Stream a response
python examples/a2a_cli.py http://localhost:8000 --stream --message "Analyze this text"

# With authentication
python examples/a2a_cli.py http://localhost:8000 --auth secret123 --message "Hello"

# Interactive mode
python examples/a2a_cli.py http://localhost:8000
```

#### Using HTTP Directly with JSON-RPC

All A2A methods use JSON-RPC 2.0 format sent to the root endpoint:

```bash
# Send a message (method: message/send)
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "message/send",
    "params": {
      "message": {
        "parts": [{"type": "text", "content": "Calculate 25 * 4"}]
      }
    }
  }'

# Get task status (method: tasks/get)
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "2",
    "method": "tasks/get",
    "params": {
      "taskId": "task-123"
    }
  }'

# Stream a message (method: message/stream)
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "3",
    "method": "message/stream",
    "params": {
      "message": {
        "parts": [{"type": "text", "content": "Generate a report"}]
      }
    }
  }'
```

#### Using Python httpx Client

```python
import httpx
import asyncio

async def send_message(agent_url: str, content: str):
    """Send a message to an A2A agent."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            agent_url,  # Root endpoint, not /v1/message/send
            json={
                "jsonrpc": "2.0",
                "id": "1",
                "method": "message/send",
                "params": {
                    "message": {
                        "parts": [{"type": "text", "content": content}]
                    }
                }
            },
            headers={"Content-Type": "application/json"}
        )
        return response.json()

# Usage
result = asyncio.run(send_message("http://localhost:8000", "Calculate 10 + 5"))
print(result)
```

## Agent-to-Agent Messaging

The CodeTether supports rich inter-agent communication through a message broker, enabling sophisticated multi-agent systems.

### Message Broker Setup

The server supports two message broker modes:

**In-Memory Broker (Development)**
```python
from a2a_server.enhanced_server import EnhancedA2AServer

# Create server with in-memory message broker
server = EnhancedA2AServer(
    agent_card=agent_card,
    use_redis=False  # Uses in-memory broker
)
```

**Redis Broker (Production)**
```python
from a2a_server.enhanced_server import EnhancedA2AServer

# Create server with Redis message broker
server = EnhancedA2AServer(
    agent_card=agent_card,
    use_redis=True,
    redis_url="redis://localhost:6379/0"
)
```

### Agent Communication Patterns

#### 1. Direct Messaging

Send messages directly from one agent to another:

```python
from a2a_server.enhanced_agents import EnhancedAgent
from a2a_server.models import Message, Part

class WorkerAgent(EnhancedAgent):
    async def process_message(self, message: Message) -> Message:
        # Process the message
        result = self.do_work(message)

        # Send result to another agent
        result_msg = Message(parts=[Part(type="text", content=f"Result: {result}")])
        await self.send_message_to_agent("Manager Agent", result_msg)

        return Message(parts=[Part(type="text", content="Work sent to manager")])
```

Agents automatically receive messages addressed to them:

```python
class ManagerAgent(EnhancedAgent):
    async def initialize(self, message_broker=None):
        await super().initialize(message_broker)
        # Agent automatically subscribes to messages addressed to it

    async def process_message(self, message: Message) -> Message:
        # This gets called when messages are received
        return Message(parts=[Part(type="text", content="Acknowledged")])
```

#### 2. Event Publishing

Broadcast events to all interested subscribers:

```python
class DataProcessorAgent(EnhancedAgent):
    async def process_message(self, message: Message) -> Message:
        # Process data
        data = self.process_data(message)

        # Publish event when processing is complete
        await self.publish_event("processing.complete", {
            "records_processed": len(data),
            "status": "success",
            "summary": data.summary
        })

        return Message(parts=[Part(type="text", content="Processing complete")])
```

#### 3. Event Subscription

Subscribe to events from specific agents:

```python
class MonitoringAgent(EnhancedAgent):
    def __init__(self, message_broker=None):
        super().__init__(
            name="Monitoring Agent",
            description="Monitors system events",
            message_broker=message_broker
        )
        self.event_count = 0

    async def initialize(self, message_broker=None):
        await super().initialize(message_broker)

        # Subscribe to processing events
        await self.subscribe_to_agent_events(
            "Data Processor Agent",
            "processing.complete",
            self.handle_processing_complete
        )

        # Subscribe to error events
        await self.subscribe_to_agent_events(
            "Data Processor Agent",
            "processing.error",
            self.handle_processing_error
        )

    async def handle_processing_complete(self, event_type: str, data: dict):
        self.event_count += 1
        print(f"Processing completed: {data['records_processed']} records")

    async def handle_processing_error(self, event_type: str, data: dict):
        self.event_count += 1
        print(f"Processing error: {data['error']}")
```

#### 4. Multi-Agent Coordination

Coordinate work across multiple agents:

```python
from a2a_server.enhanced_agents import EnhancedAgent
from a2a_server.models import Message, Part

class CoordinatorAgent(EnhancedAgent):
    """Coordinates complex workflows across multiple agents."""

    async def process_message(self, message: Message) -> Message:
        text = self._extract_text_content(message)

        if "run pipeline" in text.lower():
            # Step 1: Send to data collector
            collect_msg = Message(parts=[Part(
                type="text",
                content="Collect data from sources"
            )])
            await self.send_message_to_agent("Data Collector", collect_msg)

            # Step 2: Notify processor to be ready
            ready_msg = Message(parts=[Part(
                type="text",
                content="Prepare for incoming data"
            )])
            await self.send_message_to_agent("Data Processor", ready_msg)

            # Step 3: Publish coordination event
            await self.publish_event("pipeline.started", {
                "pipeline_id": "pipeline-123",
                "stages": ["collection", "processing", "analysis"],
                "coordinator": self.name
            })

            return Message(parts=[Part(
                type="text",
                content="Pipeline initiated across all agents"
            )])
```

### Complete Working Example

The `examples/agent_to_agent_messaging.py` file demonstrates:

1. **CoordinatorAgent**: Orchestrates work between agents
2. **DataCollectorAgent**: Collects data from multiple sources and aggregates
3. **NotificationAgent**: Monitors events and sends notifications

Run the example:

```bash
python examples/agent_to_agent_messaging.py
```

### Connecting to Remote Agents

Connect local agents to remote A2A servers using the JSON-RPC endpoint:

```bash
# Terminal 1: Start a remote A2A server on port 4400
python run_server.py run --name "Remote A2A Agent" --port 4400

# Terminal 2: Connect to it from another agent
python examples/connect_remote_agent.py --url http://localhost:4400

# Or start an interactive session
python examples/connect_remote_agent.py --url http://localhost:4400 --interactive
```

**Important**: When connecting to A2A agents programmatically, always send JSON-RPC requests to the root endpoint:

```python
# ✅ CORRECT: Send to root endpoint with JSON-RPC method
response = await client.post(
    "http://localhost:4400/",  # Root endpoint
    json={
        "jsonrpc": "2.0",
        "id": "1",
        "method": "message/send",
        "params": {"message": {...}}
    }
)

# ❌ INCORRECT: Don't use /v1/message/send endpoint
# response = await client.post("http://localhost:4400/v1/message/send", ...)
# This will result in 404 Not Found
```

The `examples/connect_remote_agent.py` demonstrates:
- Connecting to remote A2A agents via HTTP (correct JSON-RPC usage)
- Sending messages to remote agents
- Bridging local and remote agent communication
- Monitoring remote interactions
- Querying remote agent capabilities

**Expected Output:**
```
Starting Agent-to-Agent Messaging Demo
✓ Message broker started
✓ Standard agent registry initialized
✓ Custom agents initialized and subscribed to events

Demo 1: Coordinator sends messages to other agents
Coordinator response: Task coordination initiated...

Demo 2: Calculator publishes an event
Calculator published calculation.complete event
📊 NOTIFICATION: Data collected - 1 total items

Demo 3: Analysis agent publishes an event
Analysis published analysis.complete event
📊 NOTIFICATION: Data collected - 2 total items

Demo 4: Check collected data
Data Collector response:
Collected 2 data points:
- calculation from Calculator Agent
- analysis from Analysis Agent

Demo 5: Check notification count
Notification Agent response: Sent 3 notifications so far.

Demo 6: Direct agent-to-agent messaging
Coordinator sent message to Memory Agent
Memory Agent response: Stored 'Important Data' with key 'demo_key'
```

### Message Broker API Reference

#### EnhancedAgent Methods

**`send_message_to_agent(target_agent: str, message: Message)`**
- Sends a message directly to another agent
- Messages are automatically routed to the target agent's message handler

**`publish_event(event_type: str, data: Any)`**
- Publishes an event that any agent can subscribe to
- Event type is automatically prefixed with agent name

**`subscribe_to_agent_events(agent_name: str, event_type: str, handler: callable)`**
- Subscribes to events from a specific agent
- Handler is called when matching events are published

**`unsubscribe_from_agent_events(agent_name: str, event_type: str, handler: callable)`**
- Unsubscribes from previously subscribed events

### Best Practices

1. **Use Direct Messages for Request-Response**: When you need a specific agent to handle something
2. **Use Events for Notifications**: When multiple agents might be interested in state changes
3. **Always Initialize Message Broker**: Call `await agent.initialize(message_broker)`
4. **Handle Errors Gracefully**: Wrap message handlers in try-except blocks
5. **Use Typed Event Data**: Include clear structure in event data dictionaries
6. **Clean Up Subscriptions**: Unsubscribe from events when no longer needed

### Production Deployment

For production systems, use Redis message broker:

```yaml
# docker-compose.yml
services:
  redis:
    image: redis:alpine
    ports:
      - "6379:6379"

  a2a-server:
    build: .
    environment:
      - USE_REDIS=true
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis
```

Configure the server:

```python
from a2a_server.enhanced_server import EnhancedA2AServer

server = EnhancedA2AServer(
    agent_card=agent_card,
    use_redis=True,
    redis_url="redis://redis:6379/0"
)

await server.initialize_agents()
```

## Testing

### Unit Tests

```bash
# Install test dependencies
pip install -r requirements-test.txt

# Run tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=a2a_server --cov-report=html
```

### End-to-End Tests

```bash
# Run Cypress tests (requires Node.js)
npm install
npx cypress run

# Or run interactively
npx cypress open
```

### Load Testing

```bash
# Install load testing tools
pip install locust

# Run load tests (example)
locust -f tests/load_test.py --host=http://localhost:8000
```

## Monitoring and Observability

### Health Checks

The server provides comprehensive health checks:

- **Liveness**: `GET /.well-known/agent-card.json`
- **Readiness**: `GET /health/ready`
- **Detailed**: `GET /health/detail`

### Metrics

When deployed with the Helm chart, Prometheus metrics are available:

- Request/response metrics
- Task execution metrics
- MCP tool usage metrics
- System resource metrics

### Logging

Structured logging with configurable levels:

```bash
# Set log level
export A2A_LOG_LEVEL=DEBUG

# JSON structured logs for production
export A2A_LOG_FORMAT=json
```

## Security

### Authentication

Multiple authentication methods supported:

```bash
# Bearer token
A2A_AUTH_ENABLED=true
A2A_AUTH_TOKENS=client1:secret123,client2:secret456

# API key header
A2A_AUTH_HEADER=X-API-Key
A2A_AUTH_TOKENS=key1:secret123,key2:secret456
```

### Network Security

The Helm chart includes network policies:

```yaml
networkPolicy:
  enabled: true
  policyTypes:
    - Ingress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              name: allowed-namespace
```

### TLS/SSL

Configure HTTPS for production:

```yaml
ingress:
  enabled: true
  className: "nginx"
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
  hosts:
    - host: a2a.yourdomain.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: a2a-tls
      hosts:
        - a2a.yourdomain.com
```

## Development

### Project Structure

```
a2a_server/
├── __init__.py              # Package exports
├── agent_card.py            # Agent discovery and cards
├── config.py                # Configuration management
├── enhanced_agents.py       # Enhanced agent implementations
├── enhanced_server.py       # Main A2A server with MCP
├── keycloak_auth.py         # Keycloak authentication service
├── livekit_bridge.py        # Real-time communication
├── mcp_client.py            # MCP protocol client
├── mcp_server.py            # MCP server implementation
├── message_broker.py        # Redis pub/sub broker
├── enhanced_agents.py        # A2A coordination agents
├── models.py                # Pydantic data models
├── monitor_api.py           # Monitoring & CodeTether API endpoints
├── server.py                # Core A2A server
└── task_manager.py          # Task lifecycle management

agent_worker/
├── install-codetether-worker.sh  # Worker installation script (Rust binary)
├── systemd/codetether-worker.service  # Systemd service unit
├── worker.py                # DEPRECATED - legacy Python worker
├── install.sh               # DEPRECATED - legacy install script
└── config.example.json      # DEPRECATED - legacy worker configuration

examples/
├── a2a_cli.py               # Command-line client
├── agent_to_agent_messaging.py  # Agent communication demo
├── connect_remote_agent.py  # Remote agent connection
├── claude_agent.py          # Claude LLM integration
└── livekit_demo.py          # Real-time communication demo

ui/
├── monitor-tailwind.html    # Web monitoring UI
└── swift/                   # Swift iOS/macOS app
    └── A2AMonitor/

tests/
├── test_a2a_server.py       # Core server tests
├── test_agent_messaging.py  # Agent communication tests
└── test_livekit_integration.py  # LiveKit tests

chart/
└── a2a-server/              # Kubernetes Helm chart
    ├── Chart.yaml
    ├── values.yaml
    └── templates/           # K8s resource templates
```

### Custom Agent Development

Create your own enhanced agent:

```python
from a2a_server import EnhancedA2AAgent
from a2a_server.models import Message, Part

class MyCustomAgent(EnhancedA2AAgent):
    def __init__(self, name: str, mcp_client=None):
        super().__init__(name, mcp_client)

    async def _process_message(self, message: Message, skill_id: str = None) -> Message:
        # Use MCP tools
        if self.mcp_client:
            result = await self.mcp_client.call_tool("my_tool", {"input": message.parts[0].content})
            return Message(parts=[Part(type="text", content=result)])

        # Fallback processing
        return Message(parts=[Part(type="text", content="Echo: " + message.parts[0].content)])
```

### Adding MCP Tools

Integrate external MCP servers:

```python
from a2a_server.mcp_client import MCPClient

# Connect to MCP servers
mcp_client = MCPClient()
await mcp_client.connect("http://localhost:3001")  # File system tools
await mcp_client.connect("http://localhost:3002")  # Database tools

# Use in your agent
agent = MyCustomAgent("Enhanced Agent", mcp_client)
```

## Troubleshooting

### Common Issues

#### Docker Image Not Found
If you get image pull errors during Helm deployment:

```bash
# Build and tag the image
docker build -t codetether:latest .

# For Kubernetes, push to a registry
docker tag codetether:latest your-registry/codetether:latest
docker push your-registry/codetether:latest

# Update Helm values
helm upgrade --install a2a-server ./chart/a2a-server \
  --set image.repository=your-registry/a2a-server
```

#### Redis Connection Issues
If using the message broker:

```bash
# Check Redis connectivity
redis-cli -h localhost -p 6379 ping

# Use Docker Redis for development
docker run -d -p 6379:6379 redis:alpine

# Update connection string
export REDIS_URL=redis://localhost:6379/0
```

#### Port Already in Use
Change the server port:

```bash
python run_server.py run --port 8001
# or
export A2A_PORT=8001
```

#### MCP Server Connection Failed
Check MCP server availability:

```bash
# Test MCP server connectivity
curl http://localhost:3001/health

# Update MCP configuration
export MCP_SERVER_URLS=http://your-mcp-server:3001
```

### Performance Tuning

#### Production Deployment
- Use external Redis cluster for message broker
- Enable horizontal pod autoscaling
- Configure resource limits based on load
- Use persistent volumes for data

#### Memory Optimization
```yaml
resources:
  requests:
    memory: "256Mi"
    cpu: "200m"
  limits:
    memory: "512Mi"
    cpu: "500m"
```

#### Connection Pooling
```python
# Configure MCP client pooling
mcp_client = MCPClient(
    max_connections=10,
    connection_timeout=30,
    pool_recycle=3600
)
```

## Contributing

We welcome contributions to enhance the CodeTether with MCP integration!

### How to Contribute

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/amazing-feature`
3. **Make your changes**: Add features, fix bugs, improve docs
4. **Add tests**: Ensure new functionality is tested
5. **Run the test suite**: `python -m pytest tests/ -v`
6. **Update documentation**: Keep README and docs current
7. **Submit a pull request**: Describe your changes clearly

### Development Setup

```bash
# Clone your fork
git clone https://github.com/your-username/A2A-Server-MCP.git
cd A2A-Server-MCP

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows

# Install in development mode
pip install -e .
pip install -r requirements-test.txt

# Run tests
python -m pytest tests/ -v

# Run linting
flake8 a2a_server/
black a2a_server/
mypy a2a_server/
```

### Reporting Issues

- **Bug Reports**: Use GitHub Issues with detailed reproduction steps
- **Feature Requests**: Describe the use case and expected behavior
- **Security Issues**: Email security concerns privately

### Code Standards

- Follow PEP 8 style guidelines
- Use type hints for better code clarity
- Write comprehensive tests for new features
- Update documentation for API changes
- Keep commits focused and well-described

## Roadmap

### Short Term
- [ ] Enhanced MCP tool discovery and management
- [ ] WebSocket support for real-time bidirectional communication
- [ ] Advanced authentication and authorization mechanisms
- [ ] Improved error handling and recovery

### Medium Term
- [ ] Multi-tenant support for enterprise deployments
- [ ] Plugin system for custom agent behaviors
- [ ] Advanced monitoring and analytics dashboard
- [ ] Integration with popular AI frameworks

### Long Term
- [ ] Federation support for multi-cluster deployments
- [ ] AI-driven agent orchestration and load balancing
- [ ] Enhanced security with zero-trust architecture
- [ ] Support for emerging AI protocols and standards

## Community

- **Discussions**: Share ideas and ask questions in GitHub Discussions
- **Issues**: Report bugs and request features via GitHub Issues
- **Documentation**: Contribute to docs and examples
- **Code**: Submit pull requests for bug fixes and enhancements

## Running the Complete System

Here's how to run the full A2A server system with agent messaging and LLM integration across three terminals:

### Terminal 1: Start the CodeTether

```bash
cd c:/Users/riley/programming/A2A-Server-MCP
python run_server.py run --name "Remote A2A Agent" --port 4400
```

**What this does:**
- Starts the A2A server on port 4400
- Initializes the message broker (in-memory by default)
- Registers all enhanced agents (Calculator, Analysis, Memory, Media)
- Agents can now communicate with each other via the message broker
- Server exposes JSON-RPC 2.0 endpoint at `http://localhost:4400/`

**Expected output:**
```
2025-10-03 14:53:02,576 - a2a_server.message_broker - INFO - In-memory message broker started
2025-10-03 14:53:02,576 - a2a_server.enhanced_server - INFO - Message broker started (In-Memory)
2025-10-03 14:53:02,683 - a2a_server.enhanced_agents - INFO - Agent Calculator Agent initialized
2025-10-03 14:53:02,684 - a2a_server.enhanced_agents - INFO - Agent Analysis Agent initialized
INFO:     Uvicorn running on http://0.0.0.0:4400 (Press CTRL+C to quit)
```

### Terminal 2: Run Local Agent Messaging Demo

```bash
cd c:/Users/riley/programming/A2A-Server-MCP
python examples/agent_to_agent_messaging.py
```

**What this does:**
- Creates a local message broker and agent network
- Demonstrates 6 different agent communication patterns:
  1. Coordinator sending messages to Calculator/Analysis agents
  2. Calculator publishing calculation events
  3. Analysis publishing analysis events
  4. DataCollector aggregating events from multiple agents
  5. NotificationAgent tracking system events
  6. Direct agent-to-agent messaging patterns

**Expected output:**
```
Starting Agent-to-Agent Messaging Demo
✓ Message broker started
✓ Standard agent registry initialized
✓ Custom agents initialized

Demo 1: Coordinator sends messages to other agents
Coordinator response: Task coordination initiated...

Demo 2: Calculator publishes an event
Calculator published calculation.complete event
📊 NOTIFICATION: Data collected - 1 total items

Demo 5: Check notification count
Notification Agent response: Sent 3 notifications so far.
```

### Terminal 3: Connect to Remote Agent or Run Claude Demo

**Option A: Connect to the remote A2A server (from Terminal 1)**

```bash
cd c:/Users/riley/programming/A2A-Server-MCP
python examples/connect_remote_agent.py --url http://localhost:4400 --interactive
```

**What this does:**
- Connects to the remote A2A server (from Terminal 1)
- Sends messages to remote agents via JSON-RPC 2.0
- Queries remote agent capabilities
- Demonstrates cross-server agent communication

**Expected output:**
```
✓ Connected to remote agent: Remote A2A Agent
  Description: An A2A agent with MCP tool integration
  Skills: 6 available

→ User: Calculate 100 / 4
← Remote agent: The result is 25.0

Remote LLM Agent Card:
  Name: Remote A2A Agent
  Capabilities:
    - Streaming: False
    - Media: True
```

**Option B: Run Claude LLM Integration (if Claude API is on localhost:4000)**

```bash
cd c:/Users/riley/programming/A2A-Server-MCP
python examples/claude_agent.py
```

**What this does:**
- Connects to Claude API on localhost:4000
- Creates intelligent agents that use Claude for reasoning
- Demonstrates LLM-powered agent coordination
- Shows interactive Claude sessions

### Testing Your Setup

After starting the server (Terminal 1), test it from a new terminal:

```bash
# Test 1: Get the agent card
curl http://localhost:4400/.well-known/agent-card.json

# Test 2: Send a message using JSON-RPC 2.0
curl -X POST http://localhost:4400/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "message/send",
    "params": {
      "message": {
        "parts": [{"type": "text", "content": "Calculate 25 * 4"}]
      }
    }
  }'

# Test 3: List registered agents
curl http://localhost:4400/agents
```

### Common Issues and Solutions

**Issue: 404 Not Found when sending messages**

❌ **Wrong:** Sending to `/v1/message/send`
```bash
curl -X POST http://localhost:4400/v1/message/send  # This will fail!
```

✅ **Correct:** Sending JSON-RPC to root endpoint `/`
```bash
curl -X POST http://localhost:4400/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": "1", "method": "message/send", "params": {...}}'
```

**Issue: Module not found errors**

```bash
# Install dependencies
pip install -r requirements.txt
```

**Issue: Redis connection errors**

The server uses in-memory message broker by default. To use Redis:
```bash
# Start Redis
docker run -d -p 6379:6379 redis:alpine

# Set environment variable
export USE_REDIS=true
export REDIS_URL=redis://localhost:6379/0
```

## Monitor UI

The CodeTether includes a powerful real-time monitoring dashboard for agent supervision:

### Web Monitor UI

Access at `http://localhost:8000/v1/monitor/` when the server is running.

**Features:**
- Real-time message streaming via SSE
- Agent status monitoring with live updates
- Task queue management with priority levels
- Human intervention capability
- Message search and filtering
- Export to JSON/CSV
- CodeTether agent integration panel
- Session history browser
- Session resumption with context preservation
- Real-time output streaming from running tasks
- Keycloak authentication support

### Navigation

The monitor UI features a responsive sidebar navigation:

- **Dashboard**: Overview of agents, tasks, and system status
- **Agents**: List of registered agents with status indicators
- **Tasks**: Task queue with create, view, and manage capabilities
- **Sessions**: Browse and resume past CodeTether sessions
- **Codebases**: Registered codebases and their workers
- **Messages**: Real-time message log with search
- **Settings**: Configuration and preferences

### Swift Liquid Glass UI (iOS/macOS)

Native Apple platform app with a beautiful "Liquid Glass" aesthetic:

```bash
# Build for iOS/macOS
cd ui/swift/A2AMonitor
swift build -c release
```

**Features:**
- Frosted glass UI with animated gradients
- Real-time agent output streaming via SSE
- Session history with resume support
- Codebase registration and management
- Task queue with priority levels
- Watch mode for continuous agent operation
- Human intervention support
- Keycloak authentication integration

See [ui/swift/README.md](ui/swift/README.md) for full documentation.

## Distributed Agent Workers

Deploy remote agent workers that poll for tasks and execute them autonomously:

### Worker Architecture

The A2A server supports a distributed architecture where worker agents run on remote machines with access to codebases:

```
┌─────────────────────┐       ┌──────────────────────────┐
│   CodeTether        │       │   Agent Worker (VM)      │
│   (Kubernetes)      │◄─────►│   - CodeTether runtime     │
│                     │ HTTP  │   - Local codebases      │
│   - Task Queue      │       │   - Session sync         │
│   - Session Store   │       │   - Output streaming     │
│   - Auth (Keycloak) │       └──────────────────────────┘
│   - Monitor API     │              ▲
└─────────────────────┘              │
         ▲                     ┌─────┴────────────────────┐
         │                     │   CodeTether Sessions      │
    ┌────┴────┐                │   ~/.local/share/agent│
    │  Web UI │                │   └── storage/           │
    │  iOS/   │                │       ├── project/       │
    │  macOS  │                │       ├── session/       │
    └─────────┘                │       └── message/       │
                               └──────────────────────────┘
```

### Agent Worker Setup

The Agent Worker daemon runs on machines with codebases, connecting to the A2A server to receive and execute tasks.

**Quick Install (Linux):**
```bash
# Clone repository
git clone https://github.com/rileyseaburg/codetether.git
cd A2A-Server-MCP

# Run installer as root (installs codetether binary + systemd service)
sudo ./agent_worker/install-codetether-worker.sh
```

**Build from Source:**
```bash
# Build the Rust binary and install systemd service
sudo ./agent_worker/install-codetether-worker.sh --from-cargo
```

**Run Directly (no systemd):**
```bash
# One-command deploy (foreground)
./deploy-worker.sh --server https://api.codetether.run --codebases /path/to/project

# Or run the binary directly
codetether worker --server https://api.codetether.run --codebases /path/to/project --auto-approve safe --name my-worker
```

**Configure the Service:**
```bash
# Edit environment (API keys, server URL)
sudo nano /etc/codetether-worker/env

# Start the service
sudo systemctl start codetether-worker
sudo systemctl enable codetether-worker

# View logs
sudo journalctl -u codetether-worker -f
```

### 🚀 Production Worker Setup

To connect a local worker to the production CodeTether service:

1. **Deploy** (one command):
   ```bash
   # Foreground (dev/testing)
   ./deploy-worker.sh --server https://api.codetether.run --codebases /path/to/project

   # Systemd service (production)
   sudo ./deploy-worker.sh --systemd --server https://api.codetether.run --codebases /path/to/project
   ```

2. **Or install manually**:
   ```bash
   sudo ./agent_worker/install-codetether-worker.sh --codebases /path/to/project
   ```

3. **Configure** (systemd only) — edit `/etc/codetether-worker/env`:
   ```bash
   A2A_SERVER_URL=https://api.codetether.run
   A2A_CODEBASES=/path/to/project
   A2A_AUTO_APPROVE=safe
   ANTHROPIC_API_KEY=sk-ant-...   # or OPENAI_API_KEY, GOOGLE_GENERATIVE_AI_API_KEY
   ```

4. **Start the service**:
   ```bash
   sudo systemctl start codetether-worker
   ```

**What the Worker Does:**
1. **Connects** to the A2A server via SSE (Server-Sent Events)
2. **Registers** with `--codebases` paths — the server routes tasks by codebase ownership
3. **Receives** task assignments pushed from the server in real-time
4. **Executes** tasks using its built-in agentic loop (28+ tools, 8 LLM providers)
5. **Streams** real-time output back to the server

For complete documentation, see [Agent Worker Guide](codetether-docs/features/agent-worker.md).

### Session History & Resumption

Workers automatically report task results to the server, enabling:

- **Cross-Device Access**: View all past coding sessions from any device
- **Session Resumption**: Continue a conversation from where you left off
- **Real-time Output**: See agent responses as they stream in

**API Endpoints:**

```bash
# List all sessions for a codebase
curl https://api.codetether.run/v1/agent/codebases/{id}/sessions

# Get messages for a specific session
curl https://api.codetether.run/v1/agent/codebases/{id}/sessions/{session_id}/messages

# Resume a session (creates a new task)
curl -X POST https://api.codetether.run/v1/agent/codebases/{id}/sessions/{session_id}/resume \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Continue with the refactoring"}'

# Stream task output (SSE)
curl https://api.codetether.run/v1/agent/tasks/{task_id}/output/stream
```

### Real-time Output Streaming

When a task is running, you can subscribe to real-time output:

```python
import httpx
import asyncio

async def stream_output(server_url: str, task_id: str):
    """Subscribe to real-time task output via SSE."""
    url = f"{server_url}/v1/agent/tasks/{task_id}/output/stream"

    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream("GET", url) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    if data["type"] == "output":
                        print(data["content"], end="")
                    elif data["type"] == "done":
                        print("\n--- Task completed ---")
                        break

# Usage
asyncio.run(stream_output("https://api.codetether.run", "task-123"))
```

### Watch Mode

Enable watch mode for continuous task processing:

```bash
# Via API
curl -X POST http://localhost:8000/v1/agent/codebases/{id}/watch/start \
  -H "Content-Type: application/json" \
  -d '{"interval": 5}'
```

Tasks are automatically picked up and executed by the associated worker.

## Authentication

### Keycloak Integration

The A2A server supports enterprise authentication via Keycloak:

```bash
# Login with username/password
curl -X POST https://api.codetether.run/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "user@example.com", "password": "secret"}'

# Response includes JWT tokens
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "expires_in": 300,
  "user": {
    "id": "user-uuid",
    "email": "user@example.com",
    "roles": ["a2a-user", "a2a-admin"]
  }
}

# Refresh token when expired
curl -X POST https://api.codetether.run/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "eyJ..."}'
```

**Environment Configuration:**

```bash
# Keycloak settings
KEYCLOAK_URL=https://auth.example.com
KEYCLOAK_REALM=my-realm
KEYCLOAK_CLIENT_ID=a2a-monitor
KEYCLOAK_CLIENT_SECRET=your-secret
```

### Protected Endpoints

Include the access token in requests:

```bash
curl https://api.codetether.run/v1/agent/codebases \
  -H "Authorization: Bearer eyJ..."
```

## Additional Resources

- 📖 [Agent-to-Agent Messaging Quick Start Guide](docs/agent-messaging-quickstart.md)
- 📝 [Agent Messaging Implementation Details](docs/agent-messaging-implementation.md)
- 💡 [Agent-to-Agent Messaging Examples](examples/agent_to_agent_messaging.py)
- 🤖 [Claude LLM Integration Guide](docs/claude-llm-integration.md)
- 🧪 [Agent Messaging Tests](tests/test_agent_messaging.py)
- 📱 [Swift Liquid Glass UI](ui/swift/README.md)
- 🖥️ [Web Monitor UI](ui/README.md)
- 🔄 [Distributed A2A Guide](DISTRIBUTED_A2A_GUIDE.md)
- ⚡ [Distributed A2A Quickstart](DISTRIBUTED_A2A_QUICKSTART.md)
- 🔐 [Keycloak Auth Integration](a2a_server/keycloak_auth.py)

## 🚀 Production Deployment

### Deploy to api.codetether.run

Full production deployment with monitoring, autoscaling, and MCP synchronization:

```powershell
# Windows PowerShell
.\deploy-to-quantum-forge.ps1

# Linux/macOS
./deploy-to-quantum-forge.sh
```

**Features:**
- ✅ Domain: `api.codetether.run`
- ✅ TLS with Let's Encrypt
- ✅ Horizontal autoscaling (2-10 pods)
- ✅ Redis message broker
- ✅ Real-time monitoring UI
- ✅ MCP HTTP server for external agents
- ✅ Human intervention capability
- ✅ Complete audit logs
- ✅ Prometheus metrics
- ✅ Keycloak authentication
- ✅ Session history & resumption
- ✅ Real-time output streaming
- ✅ Distributed worker support

**Guides:**
- 📘 [Quantum Forge Deployment](QUANTUM_FORGE_DEPLOYMENT.md) - Complete deployment documentation
- 🚀 [Quick Start](QUANTUM_FORGE_QUICKSTART.md) - Get started in 5 minutes
- 👁️ [Monitoring UI Guide](ui/README.md) - Human oversight and intervention
- 🔧 [MCP Configuration](QUICK_REFERENCE_MCP_CONFIG.md) - Cline/external agent setup
- 🔄 [Distributed A2A Guide](DISTRIBUTED_A2A_GUIDE.md) - Multi-worker setup

**Access Production Services:**
```bash
# Monitoring dashboard
https://api.codetether.run/v1/monitor/

# Agent discovery
https://api.codetether.run/.well-known/agent-card.json

# CodeTether API
https://api.codetether.run/v1/agent/codebases

# Login (Keycloak)
curl -X POST https://api.codetether.run/v1/auth/login \
  -d '{"username": "user@example.com", "password": "secret"}'

# Health check
https://api.codetether.run/health
```

---

## Known Footguns

> **Warning**: This section documents known issues that can cause confusion or errors during development.

### File Ownership with Multi-User Development

When multiple users (e.g., `riley` and `a2a-worker`) work on the same codebase, file ownership conflicts can prevent edits:

```bash
# Check who owns a file
ls -la path/to/file.tsx

# PROBLEM: File owned by a2a-worker, but you're logged in as riley
-rw-r--r-- 1 a2a-worker a2a-worker 26426 Jan 22 18:37 AIPRDBuilder.tsx
```

**Solution**: Make files world-writable in trusted development environments:

```bash
# Fix a single file
echo "spike2" | sudo -S chmod 666 path/to/file.tsx

# Fix an entire directory recursively
echo "spike2" | sudo -S chmod -R 666 marketing-site/src/

# Or change ownership
echo "spike2" | sudo -S chown riley:riley path/to/file.tsx
```

**Why this happens**:
- The `a2a-worker` user runs automated tasks and creates/modifies files
- When you log in as `riley`, you can't edit files owned by `a2a-worker`
- This is an **open trusted workflow** - SSH, firewall, and WAF provide security at the perimeter

**Best Practice**: Set up a shared group or use `umask 000` for the worker process to create world-writable files by default:

```bash
# Add to worker's environment
umask 000
```

### JSON-RPC Endpoint Confusion

❌ **Wrong**: Sending to `/v1/message/send`
```bash
curl -X POST http://localhost:4400/v1/message/send  # 404 Not Found!
```

✅ **Correct**: Send JSON-RPC to root endpoint `/`
```bash
curl -X POST http://localhost:4400/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": "1", "method": "message/send", "params": {...}}'
```

### Session Token Expiry

Keycloak tokens expire after ~5 minutes. If API calls start returning 401:

1. The NextAuth `jwt` callback should auto-refresh tokens
2. If refresh fails, users are redirected to `/login?error=session_expired`
3. Check browser console for `Token refresh failed, signing out...`

---

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built on the [Agent2Agent Protocol](https://a2a-protocol.org) specification
- Integrates with the [Model Context Protocol](https://modelcontextprotocol.io) for tool access
- Uses [FastAPI](https://fastapi.tiangolo.com/) for high-performance web services
- Deployed with [Kubernetes](https://kubernetes.io/) and [Helm](https://helm.sh/) for scalability
- Authentication via [Keycloak](https://www.keycloak.org/) for enterprise SSO
