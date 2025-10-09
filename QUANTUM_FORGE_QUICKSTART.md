# Quantum Forge Quick Start

Get your A2A Server deployed to Quantum Forge in under 5 minutes!

## Prerequisites

✅ Docker installed  
✅ Helm 3.8+ installed  
✅ Access to `registry.quantum-forge.net`  

## Step 1: Login

```bash
# Login to Quantum Forge
docker login registry.quantum-forge.net
helm registry login registry.quantum-forge.net
```

## Step 2: Deploy

### Windows (PowerShell):
```powershell
# One command to deploy everything!
.\deploy-to-quantum-forge.ps1
```

### Linux/Mac:
```bash
# Make executable and run
chmod +x deploy-to-quantum-forge.sh
./deploy-to-quantum-forge.sh
```

**That's it!** The script will:
1. ✅ Build the Docker image
2. ✅ Tag for Quantum Forge
3. ✅ Push to `registry.quantum-forge.net/library/a2a-server:latest`
4. ✅ Package Helm chart
5. ✅ Push to `oci://registry.quantum-forge.net/library/a2a-server`

## Step 3: Install in Kubernetes

```bash
# Install from Quantum Forge
helm install a2a-server \
  oci://registry.quantum-forge.net/library/a2a-server \
  --version 0.1.0 \
  --namespace a2a-system \
  --create-namespace
```

## Step 4: Verify

```bash
# Check pods
kubectl get pods -n a2a-system

# Test A2A endpoint
kubectl port-forward -n a2a-system svc/a2a-server 8000:8000
curl http://localhost:8000/.well-known/agent-card.json

# Test MCP endpoint
kubectl port-forward -n a2a-system svc/a2a-server 9000:9000
curl http://localhost:9000/mcp/v1/tools
```

## Advanced Options

### Deploy Specific Version
```powershell
# PowerShell
.\deploy-to-quantum-forge.ps1 -Version "v1.0.0"

# Bash
VERSION="v1.0.0" ./deploy-to-quantum-forge.sh
```

### Dry Run (Preview Changes)
```powershell
# PowerShell
.\deploy-to-quantum-forge.ps1 -DryRun

# Bash
DRY_RUN=true ./deploy-to-quantum-forge.sh
```

### Skip Docker or Helm
```powershell
# Only push Helm chart
.\deploy-to-quantum-forge.ps1 -SkipDocker

# Only push Docker image
.\deploy-to-quantum-forge.ps1 -SkipHelm
```

## What Gets Deployed?

✅ **Docker Image**: `registry.quantum-forge.net/library/a2a-server:latest`
- A2A Server with MCP integration
- Port 8000: A2A Protocol
- Port 9000: MCP HTTP Server

✅ **Helm Chart**: `oci://registry.quantum-forge.net/library/a2a-server:0.1.0`
- Full Kubernetes deployment
- Redis for message broker
- Autoscaling ready
- Monitoring ready

## Next Steps

1. **Connect External Agents**: See [QUICK_REFERENCE_MCP_CONFIG.md](QUICK_REFERENCE_MCP_CONFIG.md)
2. **Configure Production**: See [QUANTUM_FORGE_DEPLOYMENT.md](QUANTUM_FORGE_DEPLOYMENT.md)
3. **Multi-Agent Setup**: See [DISTRIBUTED_A2A_GUIDE.md](DISTRIBUTED_A2A_GUIDE.md)

## Troubleshooting

### "unauthorized: authentication required"
```bash
# Re-login
docker login registry.quantum-forge.net
helm registry login registry.quantum-forge.net
```

### "connection refused"
```bash
# Check registry accessibility
ping registry.quantum-forge.net
curl https://registry.quantum-forge.net/v2/
```

### Image pull errors in Kubernetes
```bash
# Create image pull secret
kubectl create secret docker-registry quantum-forge-secret \
  --docker-server=registry.quantum-forge.net \
  --docker-username=YOUR_USERNAME \
  --docker-password=YOUR_PASSWORD \
  -n a2a-system

# Use in deployment
helm upgrade a2a-server \
  oci://registry.quantum-forge.net/library/a2a-server \
  --version 0.1.0 \
  --namespace a2a-system \
  --set imagePullSecrets[0].name=quantum-forge-secret
```

## Full Documentation

For complete details, see [QUANTUM_FORGE_DEPLOYMENT.md](QUANTUM_FORGE_DEPLOYMENT.md)
