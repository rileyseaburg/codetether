# ACP Deployment - Build & Deploy Summary

## 🎯 Objective
Deploy the A2A Server to **acp.quantum-forge.net** with full production features:
- A2A Protocol Server
- MCP HTTP Server for agent synchronization
- Real-time monitoring UI with human intervention
- TLS, autoscaling, and enterprise features

---

## 📦 Created Files

### Deployment Scripts

1. **deploy-acp.ps1** (Windows PowerShell)
   - Complete automated deployment
   - Builds Docker image
   - Pushes to Quantum Forge registry
   - Packages and deploys Helm chart
   - Configures Kubernetes resources
   - Production-ready settings

2. **deploy-acp.sh** (Linux/macOS)
   - Bash equivalent of PowerShell script
   - Same functionality for Unix systems

3. **quick-deploy-acp.ps1** (Windows)
   - Quick prerequisite checker
   - One-command deployment wrapper
   - User-friendly interface

4. **quick-deploy-acp.sh** (Linux/macOS)
   - Bash quick deploy wrapper
   - Prerequisites validation

### Documentation

5. **ACP_DEPLOYMENT.md**
   - Complete deployment guide
   - Step-by-step instructions
   - Monitoring and management
   - Troubleshooting section
   - Backup and recovery
   - External agent connection guide
   - 400+ lines of comprehensive docs

6. **QUICKSTART_ACP.md**
   - Quick reference guide
   - Essential commands
   - Fast deployment path
   - Common troubleshooting

7. **ui/README.md**
   - Monitoring UI documentation
   - Feature explanations
   - API endpoints
   - Security considerations
   - Customization guide
   - Best practices

---

## 🏗️ Deployment Architecture

```
┌─────────────────────────────────────────────────────────┐
│                 acp.quantum-forge.net                    │
│                    (LoadBalancer)                        │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────┐
        │      Ingress (Nginx)          │
        │   TLS (Let's Encrypt)         │
        └───────────┬───────────────────┘
                    │
        ┌───────────┴──────────────────┐
        │                              │
        ▼                              ▼
┌──────────────────┐          ┌──────────────────┐
│  A2A Server      │          │  MCP HTTP Server │
│  Port 8000       │          │  Port 9000       │
│  • Protocol      │          │  • JSON-RPC 2.0  │
│  • Monitoring UI │          │  • Tool Discovery│
│  • Health        │          │  • Calculator    │
│  • Agent Card    │          │  • Text Analyzer │
└────────┬─────────┘          │  • Weather       │
         │                    │  • Memory        │
         ▼                    └──────────────────┘
┌──────────────────┐
│  Redis Master    │
│  • Message Broker│
│  • Persistence   │
│  • 8Gi Volume    │
└──────────────────┘
```

**Kubernetes Resources:**
- **Namespace**: `a2a-system`
- **Deployment**: 3 replicas (production)
- **Autoscaling**: 2-10 pods based on CPU
- **Service**: LoadBalancer type
- **Ingress**: TLS enabled
- **PodDisruptionBudget**: Min 1 available
- **NetworkPolicy**: Enabled
- **ServiceMonitor**: Prometheus integration

---

## 🚀 How to Deploy

### Prerequisites

```bash
# Login to Quantum Forge registries
docker login registry.quantum-forge.net
helm registry login registry.quantum-forge.net
```

### One-Command Deploy

**Windows PowerShell:**
```powershell
.\quick-deploy-acp.ps1
```

**Linux/macOS:**
```bash
./quick-deploy-acp.sh
```

### What Happens

1. ✅ Runs tests (optional)
2. ✅ Builds Docker image with version tag
3. ✅ Tags image as `v1.0.0` and `latest`
4. ✅ Pushes to `registry.quantum-forge.net/library/a2a-server`
5. ✅ Updates Helm chart values
6. ✅ Builds Helm dependencies (Redis)
7. ✅ Packages Helm chart
8. ✅ Pushes chart to OCI registry
9. ✅ Creates `a2a-system` namespace
10. ✅ Deploys to Kubernetes with production config
11. ✅ Verifies pods are running
12. ✅ Displays LoadBalancer IP for DNS setup

---

## 📡 Deployed Services

### Primary Endpoints

| Service | URL | Purpose |
|---------|-----|---------|
| **Monitoring UI** | https://acp.quantum-forge.net/v1/monitor/ | Real-time agent oversight |
| **Agent Card** | https://acp.quantum-forge.net/.well-known/agent-card.json | Agent discovery |
| **Health Check** | https://acp.quantum-forge.net/health | System health |
| **MCP Tools List** | https://acp.quantum-forge.net:9000/mcp/v1/tools | Available MCP tools |
| **MCP JSON-RPC** | https://acp.quantum-forge.net:9000/mcp/v1/rpc | MCP endpoint |

### Agent Discovery Card Example

```json
{
  "name": "ACP Quantum Forge Agent",
  "description": "Production A2A agent with MCP integration",
  "url": "https://acp.quantum-forge.net",
  "version": "v1.0.0",
  "mcp_endpoint": "https://acp.quantum-forge.net:9000/mcp/v1/rpc",
  "capabilities": [
    "calculator",
    "text_analyzer",
    "weather_info",
    "memory_store"
  ],
  "protocols": ["a2a", "mcp"]
}
```

---

## 👁️ Monitoring Features

The monitoring UI at `/v1/monitor/` provides:

### Real-time Visibility
- Live conversation stream via Server-Sent Events
- Color-coded message types (agent/human/system/tool)
- Auto-scrolling message feed
- Agent status tracking

### Human Intervention
- Send messages to any active agent
- Override agent decisions
- Provide additional context
- Emergency stop capability

### Audit & Compliance
- Complete conversation history
- Timestamped all events
- Response time tracking
- Token usage monitoring
- Error tracking

### Export & Reporting
- JSON format (machine-readable)
- CSV format (spreadsheet)
- HTML format (human-readable)
- Real-time statistics dashboard

---

## 🔌 Connecting External Agents

### Cline/Claude Dev Configuration

Add to `cline_mcp_settings.json`:

```json
{
  "mcpServers": {
    "acp-production": {
      "command": "python",
      "args": [
        "examples/mcp_external_client.py",
        "--endpoint",
        "https://acp.quantum-forge.net:9000/mcp/v1/rpc"
      ],
      "disabled": false,
      "autoApprove": ["calculator", "text_analyzer", "weather_info"]
    }
  }
}
```

### Python Client

```python
from a2a_mcp_client import A2AMCPClient

# Connect to production
client = A2AMCPClient(
    endpoint="https://acp.quantum-forge.net:9000/mcp/v1/rpc"
)

# Use calculator tool
result = await client.calculator("multiply", 25, 4)
print(result)  # {"result": 100}

# Analyze text
analysis = await client.text_analyzer("Hello world!")
print(analysis)  # {"word_count": 2, "char_count": 12, ...}

# Store data
await client.memory_store("store", "config", {"debug": True})
data = await client.memory_store("retrieve", "config")
```

---

## 🔧 Management Commands

### View Status

```bash
# Watch pods
kubectl get pods -n a2a-system -w

# Check service
kubectl get svc -n a2a-system a2a-server

# View ingress
kubectl get ingress -n a2a-system

# Check certificate
kubectl get certificate -n a2a-system
```

### Scale Manually

```bash
# Scale to 5 replicas
kubectl scale deployment a2a-server -n a2a-system --replicas=5

# Or via Helm
helm upgrade a2a-server \
  oci://registry.quantum-forge.net/library/a2a-server \
  --version 0.1.0 \
  --namespace a2a-system \
  --set replicaCount=5 \
  --reuse-values
```

### View Logs

```bash
# All pods
kubectl logs -n a2a-system -l app.kubernetes.io/name=a2a-server -f

# Specific pod
kubectl logs -n a2a-system <pod-name> -f

# Previous pod (after crash)
kubectl logs -n a2a-system <pod-name> --previous
```

### Update Configuration

```bash
# Change log level
helm upgrade a2a-server \
  oci://registry.quantum-forge.net/library/a2a-server \
  --version 0.1.0 \
  --namespace a2a-system \
  --set env.A2A_LOG_LEVEL=DEBUG \
  --reuse-values

# Restart deployment
kubectl rollout restart deployment/a2a-server -n a2a-system
```

---

## 🔒 Security Features

### TLS/SSL
- Automatic certificate provisioning via cert-manager
- Let's Encrypt production issuer
- Forced HTTPS redirect

### Network Policies
- Namespace isolation
- Ingress/egress rules
- Redis access control

### Pod Security
- Non-root user
- Read-only filesystem
- Resource limits
- Security context

### Secrets Management
- Redis password auto-generated
- Stored in Kubernetes secrets
- Not exposed in values.yaml

---

## 📊 Production Configuration

### Resource Limits

```yaml
resources:
  limits:
    cpu: 2000m
    memory: 2Gi
  requests:
    cpu: 500m
    memory: 512Mi
```

### Autoscaling

```yaml
autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70
```

### High Availability

```yaml
podDisruptionBudget:
  enabled: true
  minAvailable: 1

affinity:
  podAntiAffinity:
    preferredDuringSchedulingIgnoredDuringExecution:
      - weight: 100
        podAffinityTerm:
          topologyKey: kubernetes.io/hostname
```

---

## 🎓 Next Steps

1. **Deploy**: Run `quick-deploy-acp.ps1` or `quick-deploy-acp.sh`
2. **Configure DNS**: Point `acp.quantum-forge.net` to LoadBalancer IP
3. **Wait for TLS**: Certificate will auto-provision (2-5 minutes)
4. **Access UI**: Open https://acp.quantum-forge.net/v1/monitor/
5. **Connect Agents**: Configure external agents with MCP endpoint
6. **Monitor**: Watch agent conversations in real-time
7. **Intervene**: Send human guidance when needed
8. **Export**: Download logs for compliance/review

---

## 📚 Documentation Index

- **Deployment**: [ACP_DEPLOYMENT.md](ACP_DEPLOYMENT.md)
- **Quick Start**: [QUICKSTART_ACP.md](QUICKSTART_ACP.md)
- **Monitoring**: [ui/README.md](ui/README.md)
- **MCP Config**: [QUICK_REFERENCE_MCP_CONFIG.md](QUICK_REFERENCE_MCP_CONFIG.md)
- **Main README**: [README.md](README.md)
- **Helm Chart**: [chart/README.md](chart/README.md)

---

## ✅ Deployment Checklist

Before running deployment:
- [ ] Docker installed and running
- [ ] Helm 3.8+ installed
- [ ] kubectl configured for target cluster
- [ ] Logged into registry.quantum-forge.net (Docker + Helm)
- [ ] Cluster has ingress-nginx installed
- [ ] Cluster has cert-manager installed
- [ ] DNS access to create A record

After deployment:
- [ ] Pods are running (`kubectl get pods -n a2a-system`)
- [ ] Service has external IP (`kubectl get svc -n a2a-system`)
- [ ] DNS A record created (acp.quantum-forge.net -> IP)
- [ ] TLS certificate issued (`kubectl get certificate -n a2a-system`)
- [ ] Health endpoint accessible (https://acp.quantum-forge.net/health)
- [ ] Monitoring UI loads (https://acp.quantum-forge.net/v1/monitor/)
- [ ] MCP tools accessible (https://acp.quantum-forge.net:9000/mcp/v1/tools)
- [ ] Agent card available (https://acp.quantum-forge.net/.well-known/agent-card.json)

---

## 🆘 Support

**Issues**: https://github.com/rileyseaburg/codetether/issues

**Logs**:
```bash
kubectl logs -n a2a-system -l app.kubernetes.io/name=a2a-server -f
```

**Health Check**:
```bash
curl https://acp.quantum-forge.net/health
```

**Monitoring**: https://acp.quantum-forge.net/v1/monitor/
