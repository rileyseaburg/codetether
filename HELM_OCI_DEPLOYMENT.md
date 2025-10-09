# Helm OCI Deployment Guide for A2A Server with MCP

This guide walks you through deploying the A2A Server to Kubernetes using Helm OCI, enabling external agents to synchronize via the MCP (Model Context Protocol) interface.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Building and Pushing the Helm Chart to OCI Registry](#building-and-pushing-the-helm-chart-to-oci-registry)
- [Deploying to Kubernetes](#deploying-to-kubernetes)
- [Configuring MCP Agent Synchronization](#configuring-mcp-agent-synchronization)
- [Connecting External Agents](#connecting-external-agents)
- [Monitoring and Troubleshooting](#monitoring-and-troubleshooting)

---

## Prerequisites

Before deploying, ensure you have:

1. **Kubernetes cluster** (minikube, kind, GKE, EKS, AKS, etc.)
2. **kubectl** configured to access your cluster
3. **Helm 3.8+** installed
4. **Docker** or compatible container runtime
5. **OCI-compliant registry access** (GitHub Container Registry, Docker Hub, Harbor, etc.)
6. **Registry credentials** configured locally

---

## Building and Pushing the Helm Chart to OCI Registry

### Step 1: Build the Docker Image

```bash
# Build the A2A server Docker image
docker build -t a2a-server:latest .

# Tag for your registry (example: GitHub Container Registry)
docker tag a2a-server:latest ghcr.io/rileyseaburg/a2a-server:latest

# Push the image
docker push ghcr.io/rileyseaburg/a2a-server:latest
```

### Step 2: Package the Helm Chart

```bash
# Navigate to the chart directory
cd chart

# Package the Helm chart
helm package a2a-server

# This creates a file like: a2a-server-0.1.0.tgz
```

### Step 3: Push Chart to OCI Registry

#### Option A: GitHub Container Registry (GHCR)

```bash
# Login to GHCR
echo $GITHUB_TOKEN | helm registry login ghcr.io -u rileyseaburg --password-stdin

# Push the chart
helm push a2a-server-0.1.0.tgz oci://ghcr.io/rileyseaburg/charts

# Verify the push
helm show chart oci://ghcr.io/rileyseaburg/charts/a2a-server --version 0.1.0
```

#### Option B: Docker Hub

```bash
# Login to Docker Hub
echo $DOCKER_PASSWORD | helm registry login registry-1.docker.io -u rileyseaburg --password-stdin

# Push the chart
helm push a2a-server-0.1.0.tgz oci://registry-1.docker.io/rileyseaburg

# Verify
helm show chart oci://registry-1.docker.io/rileyseaburg/a2a-server --version 0.1.0
```

#### Option C: Harbor

```bash
# Login to Harbor
helm registry login harbor.example.com -u admin

# Push the chart
helm push a2a-server-0.1.0.tgz oci://harbor.example.com/a2a

# Verify
helm show chart oci://harbor.example.com/a2a/a2a-server --version 0.1.0
```

---

## Deploying to Kubernetes

### Step 1: Create a Namespace

```bash
kubectl create namespace a2a-system
```

### Step 2: Create Image Pull Secrets (if using private registry)

```bash
kubectl create secret docker-registry ghcr-secret \
  --docker-server=ghcr.io \
  --docker-username=rileyseaburg \
  --docker-password=$GITHUB_TOKEN \
  --docker-email=your-email@example.com \
  -n a2a-system
```

### Step 3: Install the Chart from OCI Registry

```bash
# Install with default values
helm install a2a-server oci://ghcr.io/rileyseaburg/charts/a2a-server \
  --version 0.1.0 \
  --namespace a2a-system

# Or with custom values
helm install a2a-server oci://ghcr.io/rileyseaburg/charts/a2a-server \
  --version 0.1.0 \
  --namespace a2a-system \
  --values custom-values.yaml
```

### Step 4: Example Custom Values for Production

Create `production-values.yaml`:

```yaml
# production-values.yaml
image:
  repository: ghcr.io/rileyseaburg/a2a-server
  tag: "v1.0.0"
  pullPolicy: IfNotPresent

imagePullSecrets:
  - name: ghcr-secret

replicaCount: 3

service:
  type: LoadBalancer  # Or NodePort/ClusterIP depending on your needs
  port: 8000
  mcp:
    enabled: true
    port: 9000

ingress:
  enabled: true
  className: "nginx"
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
  hosts:
    - host: a2a.example.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: a2a-server-tls
      hosts:
        - a2a.example.com

resources:
  limits:
    cpu: 1000m
    memory: 1Gi
  requests:
    cpu: 200m
    memory: 256Mi

autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70

redis:
  enabled: true
  auth:
    enabled: true
    password: "your-redis-password"
  master:
    persistence:
      enabled: true
      size: 8Gi

env:
  A2A_LOG_LEVEL: "INFO"
  MCP_HTTP_ENABLED: "true"
  MCP_HTTP_HOST: "0.0.0.0"
  MCP_HTTP_PORT: "9000"

monitoring:
  serviceMonitor:
    enabled: true
    interval: 30s
```

Deploy with production values:

```bash
helm install a2a-server oci://ghcr.io/rileyseaburg/charts/a2a-server \
  --version 0.1.0 \
  --namespace a2a-system \
  --values production-values.yaml
```

### Step 5: Verify Deployment

```bash
# Check pod status
kubectl get pods -n a2a-system

# Check service endpoints
kubectl get svc -n a2a-system

# Check logs
kubectl logs -n a2a-system -l app.kubernetes.io/name=a2a-server --tail=100

# Test the agent card endpoint
kubectl port-forward -n a2a-system svc/a2a-server 8000:8000
curl http://localhost:8000/.well-known/agent-card.json

# Test the MCP endpoint
kubectl port-forward -n a2a-system svc/a2a-server 9000:9000
curl http://localhost:9000/mcp/v1/tools
```

---

## Configuring MCP Agent Synchronization

Once deployed, the A2A server exposes two key endpoints:

1. **A2A Protocol**: `http://a2a-server.a2a-system.svc.cluster.local:8000`
2. **MCP HTTP Interface**: `http://a2a-server.a2a-system.svc.cluster.local:9000`

### MCP Configuration for Cline/Claude Dev

To connect external AI agents (like Cline) to your deployed A2A server's MCP interface, add this to your `cline_mcp_settings.json`:

```json
{
  "mcpServers": {
    "a2a-server-mcp": {
      "command": "python",
      "args": [
        "-m",
        "a2a_mcp_client",
        "--endpoint",
        "http://a2a.example.com:9000/mcp/v1/rpc"
      ],
      "disabled": false,
      "autoApprove": [
        "calculator",
        "text_analyzer",
        "weather_info",
        "memory_store"
      ]
    }
  }
}
```

### MCP Configuration for Local Development

For local testing with port-forwarding:

```json
{
  "mcpServers": {
    "a2a-server-mcp-local": {
      "command": "python",
      "args": [
        "-m",
        "a2a_mcp_client",
        "--endpoint",
        "http://localhost:9000/mcp/v1/rpc"
      ],
      "disabled": false,
      "autoApprove": [
        "calculator",
        "text_analyzer"
      ]
    }
  }
}
```

### MCP Configuration for Kubernetes Internal Agents

For agents running inside the same Kubernetes cluster:

```json
{
  "mcpServers": {
    "a2a-server-mcp-k8s": {
      "command": "python",
      "args": [
        "-m",
        "a2a_mcp_client",
        "--endpoint",
        "http://a2a-server.a2a-system.svc.cluster.local:9000/mcp/v1/rpc"
      ],
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

---

## Connecting External Agents

### Method 1: Using the MCP HTTP Client (Python)

Install the MCP client wrapper:

```bash
pip install httpx
```

Use the client script (see `examples/mcp_external_client.py`):

```python
import asyncio
from a2a_mcp_client import A2AMCPClient

async def main():
    client = A2AMCPClient(endpoint="http://a2a.example.com:9000/mcp/v1/rpc")
    
    # List available tools
    tools = await client.list_tools()
    print(f"Available tools: {tools}")
    
    # Call calculator
    result = await client.call_tool("calculator", {
        "operation": "add",
        "a": 10,
        "b": 5
    })
    print(f"10 + 5 = {result}")
    
    await client.close()

asyncio.run(main())
```

### Method 2: Direct HTTP JSON-RPC Calls

```bash
# List available MCP tools
curl -X POST http://a2a.example.com:9000/mcp/v1/rpc \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list",
    "params": {}
  }'

# Call the calculator tool
curl -X POST http://a2a.example.com:9000/mcp/v1/rpc \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "calculator",
      "arguments": {
        "operation": "multiply",
        "a": 7,
        "b": 6
      }
    }
  }'
```

### Method 3: Agent Discovery via Agent Card

External agents can discover MCP capabilities by querying the agent card:

```bash
curl http://a2a.example.com:8000/.well-known/agent-card.json
```

The response includes MCP interface information:

```json
{
  "name": "Enhanced A2A Agent",
  "description": "An A2A agent with MCP tool integration",
  "url": "http://a2a.example.com:8000",
  "additional_interfaces": {
    "livekit": {
      "token_endpoint": "/v1/livekit/token"
    },
    "mcp": {
      "endpoint": "http://a2a.example.com:9000/mcp/v1/rpc",
      "protocol": "http",
      "description": "MCP tools including calculator, text analysis, weather info, and shared memory"
    }
  }
}
```

---

## Monitoring and Troubleshooting

### Check Deployment Status

```bash
# Get deployment status
kubectl rollout status deployment/a2a-server -n a2a-system

# View pod details
kubectl describe pod -n a2a-system -l app.kubernetes.io/name=a2a-server

# Check recent logs
kubectl logs -n a2a-system -l app.kubernetes.io/name=a2a-server --tail=50 -f
```

### Test MCP Connectivity

```bash
# Port-forward both services
kubectl port-forward -n a2a-system svc/a2a-server 8000:8000 9000:9000 &

# Test A2A endpoint
curl http://localhost:8000/.well-known/agent-card.json

# Test MCP endpoint
curl http://localhost:9000/

# List MCP tools
curl http://localhost:9000/mcp/v1/tools
```

### Common Issues

1. **MCP port not accessible**: Ensure `service.mcp.enabled: true` in values.yaml
2. **Agent card missing MCP info**: Verify enhanced mode is enabled (`app.enhanced: true`)
3. **Connection refused**: Check firewall rules and service type (LoadBalancer/NodePort)
4. **Tool calls fail**: Review pod logs for MCP HTTP server errors

### Enable Debug Logging

Update values to enable debug logging:

```yaml
env:
  A2A_LOG_LEVEL: "DEBUG"
  MCP_HTTP_ENABLED: "true"
```

Apply the change:

```bash
helm upgrade a2a-server oci://ghcr.io/rileyseaburg/charts/a2a-server \
  --version 0.1.0 \
  --namespace a2a-system \
  --values production-values.yaml \
  --reuse-values \
  --set env.A2A_LOG_LEVEL=DEBUG
```

---

## Upgrading the Deployment

```bash
# Pull the latest chart version
helm pull oci://ghcr.io/rileyseaburg/charts/a2a-server --version 0.2.0

# Upgrade the release
helm upgrade a2a-server oci://ghcr.io/rileyseaburg/charts/a2a-server \
  --version 0.2.0 \
  --namespace a2a-system \
  --values production-values.yaml

# Verify the upgrade
helm list -n a2a-system
```

---

## Uninstalling

```bash
# Uninstall the release
helm uninstall a2a-server -n a2a-system

# Delete the namespace
kubectl delete namespace a2a-system
```

---

## Next Steps

- See [examples/mcp_external_client.py](examples/mcp_external_client.py) for agent connection code
- See [DISTRIBUTED_A2A_GUIDE.md](DISTRIBUTED_A2A_GUIDE.md) for multi-agent coordination
- See [chart/a2a-server/examples/](chart/a2a-server/examples/) for more deployment examples

---

## Support

For issues, questions, or contributions:
- GitHub Issues: https://github.com/rileyseaburg/A2A-Server-MCP/issues
- Documentation: https://github.com/rileyseaburg/A2A-Server-MCP/docs
