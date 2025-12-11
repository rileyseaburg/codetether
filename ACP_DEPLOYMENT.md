# ACP Quantum Forge Deployment Guide

Complete guide for deploying the A2A Server to `acp.quantum-forge.net`.

## Quick Start

### Prerequisites

1. **Docker** - Installed and running
2. **Helm 3.8+** - Installed
3. **kubectl** - Installed and configured
4. **Access to Quantum Forge** - Registry credentials
5. **Kubernetes Cluster** - With ingress-nginx and cert-manager

### One-Command Deploy

```powershell
# Login first
docker login registry.quantum-forge.net
helm registry login registry.quantum-forge.net

# Deploy everything
.\quick-deploy-acp.ps1
```

---

## Manual Deployment

### Step 1: Login to Registries

```powershell
# Docker login
docker login registry.quantum-forge.net

# Helm login
helm registry login registry.quantum-forge.net
```

### Step 2: Run Deployment Script

```powershell
# Production deployment with all features
.\deploy-acp.ps1 -Version "v1.0.0" -Production

# Staging deployment
.\deploy-acp.ps1 -Version "v1.0.0"

# Skip tests (faster)
.\deploy-acp.ps1 -Version "v1.0.0" -Production -SkipTests

# Skip build (if image already built)
.\deploy-acp.ps1 -Version "v1.0.0" -Production -SkipBuild
```

### Step 3: Configure DNS

Get the LoadBalancer IP:

```bash
kubectl get svc -n a2a-system a2a-server
```

Configure DNS A record:
```
acp.quantum-forge.net -> <EXTERNAL-IP>
```

### Step 4: Verify Deployment

```bash
# Check pods
kubectl get pods -n a2a-system

# Check logs
kubectl logs -n a2a-system -l app.kubernetes.io/name=a2a-server -f

# Check ingress
kubectl get ingress -n a2a-system

# Test endpoints
curl https://acp.quantum-forge.net/health
curl https://acp.quantum-forge.net/.well-known/agent-card.json
```

---

## What Gets Deployed

### Docker Image
- **Name**: `registry.quantum-forge.net/library/a2a-server:v1.0.0`
- **Latest**: `registry.quantum-forge.net/library/a2a-server:latest`
- **Size**: ~500MB
- **Ports**: 8000 (A2A), 9000 (MCP)

### Kubernetes Resources

#### Production Configuration
- **Replicas**: 3 (autoscaling 2-10)
- **CPU Limits**: 2000m
- **Memory Limits**: 2Gi
- **Storage**: 8Gi Redis volume
- **LoadBalancer**: External access
- **Ingress**: TLS enabled (Let's Encrypt)

#### Staging Configuration
- **Replicas**: 2 (no autoscaling)
- **CPU Limits**: 1000m
- **Memory Limits**: 1Gi
- **Storage**: 4Gi Redis volume

### Endpoints

| Endpoint | URL | Purpose |
|----------|-----|---------|
| **Agent Card** | `https://acp.quantum-forge.net/.well-known/agent-card.json` | Agent discovery |
| **Health Check** | `https://acp.quantum-forge.net/health` | Health status |
| **Monitor UI** | `https://acp.quantum-forge.net/v1/monitor/` | Real-time monitoring |
| **MCP Tools** | `https://acp.quantum-forge.net:9000/mcp/v1/tools` | MCP tool list |
| **MCP RPC** | `https://acp.quantum-forge.net:9000/mcp/v1/rpc` | MCP JSON-RPC |

---

## Monitoring & Management

### Access Monitoring UI

Open in browser:
```
https://acp.quantum-forge.net/v1/monitor/
```

Features:
- ✅ Real-time agent conversation viewing
- ✅ Human intervention capability
- ✅ Message filtering and search
- ✅ Export logs (JSON, CSV, HTML)
- ✅ Statistics and metrics
- ✅ Agent status tracking

### View Logs

```bash
# All logs
kubectl logs -n a2a-system -l app.kubernetes.io/name=a2a-server -f

# Specific pod
kubectl logs -n a2a-system <pod-name> -f

# Previous pod logs
kubectl logs -n a2a-system <pod-name> --previous
```

### Scale Deployment

```bash
# Manual scaling
kubectl scale deployment a2a-server -n a2a-system --replicas=5

# Enable/disable autoscaling
helm upgrade a2a-server \
  oci://registry.quantum-forge.net/library/a2a-server \
  --version 0.1.0 \
  --namespace a2a-system \
  --set autoscaling.enabled=true \
  --reuse-values
```

### Update Configuration

```bash
# Update environment variable
helm upgrade a2a-server \
  oci://registry.quantum-forge.net/library/a2a-server \
  --version 0.1.0 \
  --namespace a2a-system \
  --set env.A2A_LOG_LEVEL=DEBUG \
  --reuse-values

# Restart pods
kubectl rollout restart deployment/a2a-server -n a2a-system
```

---

## Connecting External Agents

### Cline/Claude Dev Configuration

Add to `cline_mcp_settings.json`:

```json
{
  "mcpServers": {
    "acp-quantum-forge": {
      "command": "python",
      "args": [
        "examples/mcp_external_client.py",
        "--endpoint",
        "https://acp.quantum-forge.net:9000/mcp/v1/rpc"
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

### Python Client

```python
from a2a_mcp_client import A2AMCPClient

# Connect to production
client = A2AMCPClient(endpoint="https://acp.quantum-forge.net:9000/mcp/v1/rpc")

# Use tools
result = await client.calculator("add", 10, 5)
print(result)  # {"result": 15, ...}

# Shared memory
await client.memory_store("store", "task_status", "active")
```

### A2A Protocol

```python
import httpx

# Send message to agent
response = await httpx.post(
    "https://acp.quantum-forge.net/",
    json={
        "jsonrpc": "2.0",
        "id": "1",
        "method": "message/send",
        "params": {
            "message": {
                "parts": [{"type": "text", "content": "Calculate 25 * 4"}]
            }
        }
    }
)
```

---

## Troubleshooting

### Pods Not Starting

```bash
# Describe pod
kubectl describe pod -n a2a-system <pod-name>

# Check events
kubectl get events -n a2a-system --sort-by='.lastTimestamp'

# Check resource constraints
kubectl top pods -n a2a-system
```

### Image Pull Errors

```bash
# Create image pull secret
kubectl create secret docker-registry quantum-forge-secret \
  --docker-server=registry.quantum-forge.net \
  --docker-username=YOUR_USERNAME \
  --docker-password=YOUR_PASSWORD \
  -n a2a-system

# Update deployment
helm upgrade a2a-server \
  oci://registry.quantum-forge.net/library/a2a-server \
  --version 0.1.0 \
  --namespace a2a-system \
  --set imagePullSecrets[0].name=quantum-forge-secret \
  --reuse-values
```

### TLS Certificate Issues

```bash
# Check certificate
kubectl get certificate -n a2a-system

# Describe certificate
kubectl describe certificate acp-quantum-forge-tls -n a2a-system

# Check cert-manager logs
kubectl logs -n cert-manager -l app=cert-manager -f
```

### LoadBalancer Pending

```bash
# Check service
kubectl describe svc a2a-server -n a2a-system

# If on-premise, use NodePort instead
helm upgrade a2a-server \
  oci://registry.quantum-forge.net/library/a2a-server \
  --version 0.1.0 \
  --namespace a2a-system \
  --set service.type=NodePort \
  --reuse-values
```

### Monitoring UI Not Loading

```bash
# Port-forward for testing
kubectl port-forward -n a2a-system svc/a2a-server 8000:8000

# Access locally
# http://localhost:8000/v1/monitor/

# Check if ui directory exists
kubectl exec -n a2a-system <pod-name> -- ls -la /app/ui
```

---

## Backup & Recovery

### Backup Redis Data

```bash
# Exec into Redis pod
kubectl exec -it -n a2a-system a2a-server-redis-master-0 -- /bin/bash

# Create backup
redis-cli SAVE
cp /data/dump.rdb /tmp/backup.rdb

# Copy backup out
kubectl cp a2a-system/a2a-server-redis-master-0:/tmp/backup.rdb ./redis-backup.rdb
```

### Backup Logs

```bash
# Export logs from monitoring UI
curl https://acp.quantum-forge.net/v1/monitor/export/json > logs.json

# Or via kubectl
kubectl logs -n a2a-system -l app.kubernetes.io/name=a2a-server --tail=-1 > logs.txt
```

### Restore Deployment

```bash
# Rollback to previous version
helm rollback a2a-server -n a2a-system

# Rollback to specific revision
helm rollback a2a-server 2 -n a2a-system

# View history
helm history a2a-server -n a2a-system
```

---

## Upgrading

### Deploy New Version

```powershell
# Build and deploy new version
.\deploy-acp.ps1 -Version "v1.1.0" -Production

# Or update existing
helm upgrade a2a-server \
  oci://registry.quantum-forge.net/library/a2a-server \
  --version 0.2.0 \
  --namespace a2a-system \
  --reuse-values
```

### Zero-Downtime Updates

```bash
# Ensure HPA and PDB are enabled
helm upgrade a2a-server \
  oci://registry.quantum-forge.net/library/a2a-server \
  --version 0.1.0 \
  --namespace a2a-system \
  --set autoscaling.enabled=true \
  --set podDisruptionBudget.enabled=true \
  --set podDisruptionBudget.minAvailable=1 \
  --reuse-values

# Rolling update will happen automatically
```

---

## Uninstalling

```bash
# Delete Helm release
helm uninstall a2a-server -n a2a-system

# Delete namespace (WARNING: deletes all data)
kubectl delete namespace a2a-system

# Delete images from registry
docker rmi registry.quantum-forge.net/library/a2a-server:v1.0.0
docker rmi registry.quantum-forge.net/library/a2a-server:latest
```

---

## Support & Documentation

- **Main README**: [README.md](README.md)
- **Helm Chart Docs**: [chart/README.md](chart/README.md)
- **MCP Guide**: [MCP_AGENT_SYNC_SUMMARY.md](MCP_AGENT_SYNC_SUMMARY.md)
- **Monitoring Guide**: [ui/README.md](ui/README.md)
- **Quantum Forge Deployment**: [QUANTUM_FORGE_DEPLOYMENT.md](QUANTUM_FORGE_DEPLOYMENT.md)

For issues:
- GitHub: https://github.com/rileyseaburg/codetether/issues
- Logs: `kubectl logs -n a2a-system -l app.kubernetes.io/name=a2a-server`
