# Quick Deploy Guide - acp.quantum-forge.net

## Prerequisites

Ensure you have:
- ✅ Docker installed and running
- ✅ Helm 3.8+ installed  
- ✅ kubectl configured
- ✅ Access to registry.quantum-forge.net
- ✅ Kubernetes cluster with ingress-nginx and cert-manager

## Login to Registries

```bash
# Docker login
docker login registry.quantum-forge.net

# Helm login  
helm registry login registry.quantum-forge.net
```

## Deploy (Windows PowerShell)

```powershell
# Quick deploy
.\quick-deploy-acp.ps1

# Or manual
.\deploy-acp.ps1 -Version "v1.0.0" -Production
```

## Deploy (Linux/macOS)

```bash
# Quick deploy
./quick-deploy-acp.sh

# Or manual
PRODUCTION=true ./deploy-acp.sh
```

## What Gets Deployed

- **Image**: `registry.quantum-forge.net/library/a2a-server:v1.0.0`
- **Domain**: `acp.quantum-forge.net`
- **Namespace**: `a2a-system`
- **Replicas**: 3 (production) with autoscaling
- **Features**:
  - A2A Protocol Server (port 8000)
  - MCP HTTP Server (port 9000)
  - Real-time Monitoring UI
  - TLS via Let's Encrypt
  - Redis for message broker
  - Prometheus metrics

## Verify Deployment

```bash
# Watch pods start
kubectl get pods -n a2a-system -w

# Get LoadBalancer IP
kubectl get svc -n a2a-system a2a-server

# Check logs
kubectl logs -n a2a-system -l app.kubernetes.io/name=a2a-server -f
```

## Configure DNS

Once you have the LoadBalancer IP:

```bash
# Get IP
EXTERNAL_IP=$(kubectl get svc -n a2a-system a2a-server -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
echo $EXTERNAL_IP
```

Create DNS A record:
```
acp.quantum-forge.net -> <EXTERNAL-IP>
```

## Access Services

After DNS propagates and certificate is issued:

- **Health**: https://acp.quantum-forge.net/health
- **Agent Card**: https://acp.quantum-forge.net/.well-known/agent-card.json
- **Monitor UI**: https://acp.quantum-forge.net/v1/monitor/
- **MCP Tools**: https://acp.quantum-forge.net:9000/mcp/v1/tools

## Troubleshooting

### Pods not starting
```bash
kubectl describe pod -n a2a-system <pod-name>
kubectl logs -n a2a-system <pod-name>
```

### Certificate not issuing
```bash
kubectl get certificate -n a2a-system
kubectl describe certificate acp-quantum-forge-tls -n a2a-system
```

### LoadBalancer pending
```bash
# Check service
kubectl describe svc -n a2a-system a2a-server

# If on-premise, switch to NodePort
helm upgrade a2a-server \
  oci://registry.quantum-forge.net/library/a2a-server \
  --version 0.1.0 \
  --namespace a2a-system \
  --set service.type=NodePort \
  --reuse-values
```

## Full Documentation

See [ACP_DEPLOYMENT.md](ACP_DEPLOYMENT.md) for complete guide.
