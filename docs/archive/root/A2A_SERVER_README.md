# A2A Server Implementation

A complete implementation of the Agent2Agent (A2A) protocol with message broker functionality for inter-agent communication.

## Features

- **Full A2A Protocol Support**: JSON-RPC 2.0 over HTTP(S) with all core methods
- **Agent Discovery**: Agent Cards with capability advertisement
- **Real-time Communication**: Server-Sent Events (SSE) for streaming
- **Message Broker**: Redis-based pub/sub for agent coordination
- **Task Management**: Comprehensive task lifecycle handling
- **Security**: HTTP authentication and authorization support
- **Enterprise-Ready**: Kubernetes deployment with Helm chart
- **Production Features**: Health checks, monitoring, autoscaling, network policies
- **Extensible**: Easy to customize with your own agent logic

## Quick Start

### Option 1: Kubernetes Deployment (Recommended)

Deploy using the included Helm chart for a production-ready setup:

```bash
# Add Helm repository and build dependencies
helm repo add bitnami https://charts.bitnami.com/bitnami
cd chart/a2a-server
helm dependency build
cd ../..

# Development deployment
helm install a2a-dev chart/a2a-server/ \
  --values chart/a2a-server/examples/values-dev.yaml \
  --namespace a2a-dev --create-namespace

# Production deployment
helm install a2a-prod chart/a2a-server/ \
  --values chart/a2a-server/examples/values-prod.yaml \
  --namespace production --create-namespace
```

See the [Helm Chart README](chart/README.md) for detailed configuration options.

### Option 2: Docker Deployment

```bash
# Build the image
docker build -t a2a-server .

# Run with default configuration
docker run -p 8000:8000 a2a-server

# Run with custom environment
docker run -p 8000:8000 \
  -e A2A_AGENT_NAME="My Agent" \
  -e A2A_LOG_LEVEL="DEBUG" \
  a2a-server
```

### Option 3: Local Development

#### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

#### 2. Run a Simple Echo Agent

```bash
python run_server.py run --name "My Echo Agent" --port 8000
```

#### 3. Test the Agent

```bash
# View agent card
curl http://localhost:8000/.well-known/agent-card.json

# Send a message using the CLI
python examples/a2a_cli.py http://localhost:8000 --message "Hello, agent!"

# Interactive mode
python examples/a2a_cli.py http://localhost:8000
```

## Architecture

### Core Components

- **A2AServer**: Main server implementing the A2A protocol
- **TaskManager**: Handles task lifecycle and state management
- **MessageBroker**: Provides pub/sub messaging for agent communication
- **AgentCard**: Manages agent discovery and capability advertisement

### Message Broker Features

- Agent registration and discovery
- Real-time event streaming
- Task status updates
- Inter-agent message routing
- Redis backend for scalability

## Configuration

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Key settings:
- `A2A_HOST`: Server host (default: 0.0.0.0)
- `A2A_PORT`: Server port (default: 8000)
- `A2A_REDIS_URL`: Redis connection string
- `A2A_AUTH_ENABLED`: Enable authentication
- `A2A_AUTH_TOKENS`: Comma-separated auth tokens

## Examples

### Running Multiple Agents

```bash
# Start multiple example agents
python run_server.py multi
```

This starts echo agents on ports 8001, 8002, and 8003.

### Custom Agent Implementation

```python
from a2a_server import A2AServer, CustomA2AAgent
from a2a_server.models import Message, Part

class MyCustomAgent(CustomA2AAgent):
    async def _process_message(self, message: Message, skill_id: str = None) -> Message:
        # Your custom logic here
        response_parts = []
        for part in message.parts:
            if part.type == "text":
                response_parts.append(Part(
                    type="text",
                    content=f"Processed: {part.content}"
                ))
        return Message(parts=response_parts)
```

### Using the Message Broker

```python
from a2a_server.message_broker import MessageBroker

# Subscribe to agent events
async def on_agent_registered(event_type, data):
    print(f"New agent registered: {data['agent_name']}")

await broker.subscribe_to_events("agent.registered", on_agent_registered)

# Discover other agents
agents = await broker.discover_agents()
for agent in agents:
    print(f"Found agent: {agent.name}")
```

## A2A Protocol Methods

The server implements all core A2A methods:

- `message/send`: Send a message and get a response
- `message/stream`: Send a message with streaming updates
- `tasks/get`: Get task information
- `tasks/cancel`: Cancel a running task
- `tasks/resubscribe`: Reconnect to a streaming task

## Testing

Run the test suite:

```bash
pip install -r requirements-test.txt
python -m pytest tests/ -v
```

## Agent Discovery

Agents automatically register with the message broker and can be discovered:

```bash
# List all registered agents
curl http://localhost:8000/agents

# Get specific agent card
curl http://localhost:8000/.well-known/agent-card.json
```

## Streaming Support

Example of streaming communication:

```bash
python examples/a2a_cli.py http://localhost:8000 --stream --message "Process this with updates"
```

## Security

### Authentication

Enable authentication in `.env`:

```
A2A_AUTH_ENABLED=true
A2A_AUTH_TOKENS=client1:secret123,client2:secret456
```

Use with CLI:

```bash
python examples/a2a_cli.py http://localhost:8000 --auth secret123 --message "Hello"
```

### Authorization (OPA Policy Engine)

The server uses **Open Policy Agent (OPA)** for centralized, fine-grained authorization:

- **RBAC model**: 5 roles — `admin`, `a2a-admin`, `operator`, `editor`, `viewer`
- **Permissions**: `resource:action` format (e.g., `task:read`, `agent:admin`)
- **Centralized middleware**: `PolicyAuthorizationMiddleware` maps all ~160 API routes to required permissions
- **Rego policies**: `policies/` directory contains RBAC, API key scope, and tenant isolation rules
- **OPA sidecar**: Kubernetes deployments run OPA as a sidecar; local dev uses a built-in fallback evaluator

Enable OPA in your Helm values:

```yaml
opa:
  enabled: true
  image: openpolicyagent/opa:1.3.0-static
```

Test authorization policies:

```bash
make policy-test
```

See [Policy Engine Documentation](codetether-docs/auth/policy-engine.md) for the full RBAC matrix, Rego policy reference, and extension guide.

### HTTPS

For production, use a reverse proxy (nginx, Apache) or configure uvicorn with SSL certificates.

## Development

### Project Structure

```
a2a_server/
├── __init__.py          # Package exports
├── models.py            # Pydantic models for A2A protocol
├── server.py            # Main A2A server implementation
├── task_manager.py      # Task lifecycle management
├── message_broker.py    # Redis-based message broker
├── agent_card.py        # Agent card creation and management
├── config.py            # Configuration management
├── policy.py            # OPA policy client + require_permission()
└── policy_middleware.py  # Centralized authorization middleware

examples/
├── example_agents.py    # Sample agent implementations
└── a2a_cli.py          # Command-line client

tests/
└── test_a2a_server.py  # Test suite
```

### Adding Custom Skills

```python
# In your agent card
agent_card = (create_agent_card(...)
    .with_skill(
        skill_id="my-skill",
        name="My Custom Skill",
        description="Does something useful",
        input_modes=["text", "file"],
        output_modes=["text", "data"]
    )
    .build())
```

## Troubleshooting

### Redis Connection Issues

If using Redis message broker and getting connection errors:

1. Install Redis: `sudo apt-get install redis-server` (Ubuntu) or `brew install redis` (macOS)
2. Start Redis: `redis-server`
3. Test connection: `redis-cli ping`

### Port Already in Use

Change the port in your command:

```bash
python run_server.py run --port 8001
```

### Authentication Errors

Check your auth token configuration and ensure the token is included in requests.

## Deployment Environments

The Helm chart supports multiple deployment configurations:

### Development Environment
- Single replica with minimal resources
- Included Redis instance
- NodePort service for easy access
- Debug logging enabled
- No authentication required

```bash
helm install a2a-dev chart/a2a-server/ \
  --values chart/a2a-server/examples/values-dev.yaml
```

### Staging Environment
- Two replicas for testing reliability
- Persistent Redis storage
- Ingress with staging TLS certificates
- Authentication enabled
- Production-like monitoring

```bash
helm install a2a-staging chart/a2a-server/ \
  --values chart/a2a-server/examples/values-staging.yaml
```

### Production Environment
- High availability with 3+ replicas
- External Redis cluster
- Production TLS certificates
- Full authentication and authorization
- Comprehensive monitoring and alerting
- Network policies and security controls
- Horizontal pod autoscaling

```bash
helm install a2a-prod chart/a2a-server/ \
  --values chart/a2a-server/examples/values-prod.yaml
```

For detailed configuration options, see the [Helm Chart Documentation](chart/README.md).

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Run the test suite
5. Submit a pull request

## License

Apache 2.0 License - see LICENSE file for details.
