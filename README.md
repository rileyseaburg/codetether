# A2A Server with MCP Integration

[![Apache License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-supported-blue.svg)](https://www.docker.com/)
[![Kubernetes](https://img.shields.io/badge/kubernetes-ready-blue.svg)](https://kubernetes.io/)

**A production-ready Agent2Agent (A2A) server implementation with Model Context Protocol (MCP) tool integration for enhanced agent capabilities.**

This repository provides a complete A2A protocol server that bridges the gap between AI agents and external tools through MCP integration. The server enables agents to communicate using the standardized A2A protocol while accessing a rich ecosystem of tools via the Model Context Protocol.

## Key Features

- **🔗 Full A2A Protocol Support**: Complete implementation of Agent2Agent communication standard
- **🛠️ MCP Tool Integration**: Access external tools and resources through Model Context Protocol
- **🤖 LLM Integration**: Connect Claude or other LLMs for intelligent agent coordination
- **📡 Real-time Communication**: Server-Sent Events (SSE) for streaming responses
- **💬 Agent-to-Agent Messaging**: Publish/subscribe and direct messaging between agents
- **🚀 Production Ready**: Kubernetes deployment with Helm charts
- **🔐 Enterprise Security**: Authentication, authorization, and network policies
- **📊 Observability**: Built-in monitoring, health checks, and metrics
- **⚡ Scalable**: Redis-based message broker with horizontal scaling
- **🐳 Container Native**: Docker and Kubernetes optimized

## Quick Start

### �️ Local Development (Recommended for Getting Started)

**Terminal 1: Run the A2A Server**
```bash
# Install dependencies
pip install -r requirements.txt

# Run the server with enhanced agents
python run_server.py run --name "A2A MCP Agent" --port 8000

# The server will start with:
# - Calculator Agent (math operations)
# - Analysis Agent (text analysis, weather)
# - Memory Agent (data storage)
# - Media Agent (LiveKit sessions)
```

**Terminal 2: Run Agent-to-Agent Messaging Demo**
```bash
# Run the comprehensive agent messaging demo
python examples/agent_to_agent_messaging.py

# This demonstrates:
# - Direct agent-to-agent messaging
# - Event publishing and subscribing
# - Multi-agent coordination
# - Data aggregation across agents
```

**Terminal 3: Connect with Claude LLM**
```bash
# Run Claude integration demo (requires Claude API on localhost:4000)
python examples/claude_agent.py

# Or connect to a remote A2A server
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

### �🐳 Docker Deployment

The fastest way to get started with Docker:

```bash
# Build the Docker image
docker build -t a2a-server:latest .

# Run with default configuration
docker run -p 8000:8000 a2a-server:latest

# Test the server
curl http://localhost:8000/.well-known/agent-card.json
```

### ☸️ Kubernetes Deployment (Production)

Deploy to Kubernetes using the included Helm chart. For complete OCI registry deployment and external agent synchronization, see **[HELM_OCI_DEPLOYMENT.md](HELM_OCI_DEPLOYMENT.md)**.

**Quick Install (Local Chart):**

```bash
# Build and tag the image for your registry
docker build -t your-registry/a2a-server:latest .
docker push your-registry/a2a-server:latest

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

- **Enhanced A2A Server**: Extended A2A protocol implementation with MCP integration
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

# Redis Configuration (for message broker)
REDIS_URL=redis://localhost:6379/0
USE_REDIS=false  # Set to true to use Redis, false for in-memory broker

# Authentication (optional)
A2A_AUTH_ENABLED=false
A2A_AUTH_TOKENS=client1:secret123,client2:secret456
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

The A2A Server supports rich inter-agent communication through a message broker, enabling sophisticated multi-agent systems.

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
├── agent_card.py           # Agent discovery and cards
├── config.py               # Configuration management
├── enhanced_agents.py      # Enhanced agent implementations
├── enhanced_server.py      # Main A2A server with MCP
├── livekit_bridge.py       # Real-time communication
├── mcp_client.py           # MCP protocol client
├── mcp_server.py           # MCP server implementation
├── message_broker.py       # Redis pub/sub broker
├── mock_mcp.py            # MCP mocking for tests
├── models.py              # Pydantic data models
├── server.py              # Core A2A server
└── task_manager.py        # Task lifecycle management

examples/
├── a2a_cli.py             # Command-line client
├── example_agents.py      # Sample implementations
└── livekit_demo.py        # Real-time communication demo

tests/
├── test_a2a_server.py     # Core server tests
└── test_livekit_integration.py  # LiveKit tests

chart/
└── a2a-server/            # Kubernetes Helm chart
    ├── Chart.yaml
    ├── values.yaml
    └── templates/         # K8s resource templates
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
docker build -t a2a-server:latest .

# For Kubernetes, push to a registry
docker tag a2a-server:latest your-registry/a2a-server:latest
docker push your-registry/a2a-server:latest

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

We welcome contributions to enhance the A2A Server with MCP integration!

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

### Terminal 1: Start the A2A Server

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

## Additional Resources

- 📖 [Agent-to-Agent Messaging Quick Start Guide](docs/agent-messaging-quickstart.md)
- 📝 [Agent Messaging Implementation Details](docs/agent-messaging-implementation.md)
- 💡 [Agent-to-Agent Messaging Examples](examples/agent_to_agent_messaging.py)
- 🤖 [Claude LLM Integration Guide](docs/claude-llm-integration.md)
- 🧪 [Agent Messaging Tests](tests/test_agent_messaging.py)

## 🚀 Production Deployment

### Deploy to acp.quantum-forge.net

Full production deployment with monitoring, autoscaling, and MCP synchronization:

```powershell
# Windows PowerShell
.\quick-deploy-acp.ps1

# Linux/macOS
./quick-deploy-acp.sh
```

**Features:**
- ✅ Domain: `acp.quantum-forge.net`
- ✅ TLS with Let's Encrypt
- ✅ Horizontal autoscaling (2-10 pods)
- ✅ Redis message broker
- ✅ Real-time monitoring UI
- ✅ MCP HTTP server for external agents
- ✅ Human intervention capability
- ✅ Complete audit logs
- ✅ Prometheus metrics

**Guides:**
- 📘 [ACP Deployment Guide](ACP_DEPLOYMENT.md) - Complete deployment documentation
- 🚀 [Quick Start](QUICKSTART_ACP.md) - Get started in 5 minutes
- 👁️ [Monitoring UI Guide](ui/README.md) - Human oversight and intervention
- 🔧 [MCP Configuration](QUICK_REFERENCE_MCP_CONFIG.md) - Cline/external agent setup

**Access Production Services:**
```bash
# Monitoring dashboard
https://acp.quantum-forge.net/v1/monitor/

# Agent discovery
https://acp.quantum-forge.net/.well-known/agent-card.json

# MCP tools endpoint
https://acp.quantum-forge.net:9000/mcp/v1/tools

# Health check
https://acp.quantum-forge.net/health
```

---

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built on the [Agent2Agent Protocol](https://a2a-protocol.org) specification
- Integrates with the [Model Context Protocol](https://modelcontextprotocol.io) for tool access
- Uses [FastAPI](https://fastapi.tiangolo.com/) for high-performance web services
- Deployed with [Kubernetes](https://kubernetes.io/) and [Helm](https://helm.sh/) for scalability
