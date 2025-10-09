# Quantum Forge Registry Deployment Guide

This guide explains how to deploy the A2A Server to the Quantum Forge registry at `registry.quantum-forge.net`.

## Prerequisites

1. **Docker** installed and running
2. **Helm 3.8+** installed
3. **Access to Quantum Forge registry**
4. **Kubernetes cluster** (optional, for deployment)

## Quick Start

### 1. Login to Quantum Forge Registry

```bash
# Docker login
docker login registry.quantum-forge.net

# Helm registry login
helm registry login registry.quantum-forge.net
```

### 2. Deploy Using Script

**Windows (PowerShell):**
```powershell
# Deploy with default settings (version: latest)
.\deploy-to-quantum-forge.ps1

# Deploy with specific version
.\deploy-to-quantum-forge.ps1 -Version "v1.0.0"

# Dry run (see what would be done)
.\deploy-to-quantum-forge.ps1 -DryRun

# Skip Docker, only push Helm chart
.\deploy-to-quantum-forge.ps1 -SkipDocker

# Skip Helm, only push Docker image
.\deploy-to-quantum-forge.ps1 -SkipHelm
```

**Linux/Mac (Bash):**
```bash
# Make script executable
chmod +x deploy-to-quantum-forge.sh

# Deploy with default settings
./deploy-to-quantum-forge.sh

# Deploy with specific version
VERSION="v1.0.0" ./deploy-to-quantum-forge.sh

# Dry run
DRY_RUN=true ./deploy-to-quantum-forge.sh

# Skip Docker, only push Helm chart
SKIP_DOCKER=true ./deploy-to-quantum-forge.sh
```

---

## Manual Deployment Steps

### Step 1: Build Docker Image

```bash
docker build -t a2a-server:latest .
```

### Step 2: Tag for Quantum Forge

```bash
# Tag the image
docker tag a2a-server:latest registry.quantum-forge.net/library/a2a-server:latest

# Or with a specific version
docker tag a2a-server:latest registry.quantum-forge.net/library/a2a-server:v1.0.0
```

### Step 3: Push Docker Image

```bash
# Push to Quantum Forge
docker push registry.quantum-forge.net/library/a2a-server:latest

# Or with version tag
docker push registry.quantum-forge.net/library/a2a-server:v1.0.0
```

### Step 4: Package Helm Chart

```bash
# Navigate to chart directory and build dependencies
cd chart/a2a-server
helm dependency build
cd ../..

# Package the chart
helm package chart/a2a-server
```

This creates: `a2a-server-0.1.0.tgz`

### Step 5: Push Helm Chart

```bash
# Push to Quantum Forge OCI registry
helm push a2a-server-0.1.0.tgz oci://registry.quantum-forge.net/library
```

---

## Installing from Quantum Forge Registry

### Pull Docker Image

```bash
# Pull the latest image
docker pull registry.quantum-forge.net/library/a2a-server:latest

# Or specific version
docker pull registry.quantum-forge.net/library/a2a-server:v1.0.0

# Run locally
docker run -p 8000:8000 -p 9000:9000 \
  -e MCP_HTTP_ENABLED=true \
  registry.quantum-forge.net/library/a2a-server:latest
```

### Install Helm Chart

```bash
# Install from Quantum Forge OCI registry
helm install a2a-server \
  oci://registry.quantum-forge.net/library/a2a-server \
  --version 0.1.0 \
  --namespace a2a-system \
  --create-namespace
```

### Install with Custom Values

Create `quantum-forge-values.yaml`:

```yaml
image:
  repository: registry.quantum-forge.net/library/a2a-server
  tag: "v1.0.0"
  pullPolicy: Always

service:
  type: LoadBalancer
  port: 8000
  mcp:
    enabled: true
    port: 9000

env:
  A2A_LOG_LEVEL: "INFO"
  MCP_HTTP_ENABLED: "true"
  MCP_HTTP_PORT: "9000"

resources:
  limits:
    cpu: 1000m
    memory: 1Gi
  requests:
    cpu: 200m
    memory: 256Mi
```

Install:

```bash
helm install a2a-server \
  oci://registry.quantum-forge.net/library/a2a-server \
  --version 0.1.0 \
  --namespace a2a-system \
  --create-namespace \
  --values quantum-forge-values.yaml
```

---

## Verification

### Verify Docker Image

```bash
# List images
docker images | grep quantum-forge

# Inspect the image
docker inspect registry.quantum-forge.net/library/a2a-server:latest

# Test run
docker run --rm -p 8000:8000 -p 9000:9000 \
  registry.quantum-forge.net/library/a2a-server:latest
```

### Verify Helm Chart

```bash
# Show chart info
helm show chart oci://registry.quantum-forge.net/library/a2a-server --version 0.1.0

# Show chart values
helm show values oci://registry.quantum-forge.net/library/a2a-server --version 0.1.0

# Show all chart info
helm show all oci://registry.quantum-forge.net/library/a2a-server --version 0.1.0
```

### Verify Kubernetes Deployment

```bash
# Check pod status
kubectl get pods -n a2a-system

# Check service endpoints
kubectl get svc -n a2a-system

# View logs
kubectl logs -n a2a-system -l app.kubernetes.io/name=a2a-server --tail=50

# Test A2A endpoint
kubectl port-forward -n a2a-system svc/a2a-server 8000:8000
curl http://localhost:8000/.well-known/agent-card.json

# Test MCP endpoint
kubectl port-forward -n a2a-system svc/a2a-server 9000:9000
curl http://localhost:9000/mcp/v1/tools
```

---

## Environment Variables

The deployment scripts support these environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `VERSION` | `latest` | Image/chart version tag |
| `REGISTRY` | `registry.quantum-forge.net` | Registry URL |
| `PROJECT` | `library` | Registry project/namespace |
| `IMAGE_NAME` | `a2a-server` | Image name |
| `SKIP_BUILD` | `false` | Skip Docker build step |
| `SKIP_DOCKER` | `false` | Skip Docker push |
| `SKIP_HELM` | `false` | Skip Helm push |
| `DRY_RUN` | `false` | Show commands without executing |

**Example with custom values:**

```bash
# PowerShell
.\deploy-to-quantum-forge.ps1 -Version "v2.0.0" -Project "production"

# Bash
VERSION="v2.0.0" PROJECT="production" ./deploy-to-quantum-forge.sh
```

---

## Using Podman (Alternative to Docker)

If you prefer Podman over Docker:

```bash
# Build with Podman
podman build -t a2a-server:latest .

# Tag for Quantum Forge
podman tag a2a-server:latest registry.quantum-forge.net/library/a2a-server:latest

# Push to Quantum Forge
podman push registry.quantum-forge.net/library/a2a-server:latest
```

---

## Troubleshooting

### Authentication Issues

```bash
# Re-login to Docker registry
docker logout registry.quantum-forge.net
docker login registry.quantum-forge.net

# Re-login to Helm registry
helm registry logout registry.quantum-forge.net
helm registry login registry.quantum-forge.net
```

### Image Pull Errors in Kubernetes

If pods fail to pull the image:

```bash
# Create image pull secret
kubectl create secret docker-registry quantum-forge-secret \
  --docker-server=registry.quantum-forge.net \
  --docker-username=YOUR_USERNAME \
  --docker-password=YOUR_PASSWORD \
  --docker-email=YOUR_EMAIL \
  -n a2a-system

# Update Helm values to use the secret
helm upgrade a2a-server \
  oci://registry.quantum-forge.net/library/a2a-server \
  --version 0.1.0 \
  --namespace a2a-system \
  --set imagePullSecrets[0].name=quantum-forge-secret \
  --reuse-values
```

### Chart Push Failures

```bash
# Verify Helm version (must be 3.8+)
helm version

# Re-login to registry
helm registry login registry.quantum-forge.net

# Try with explicit OCI prefix
helm push a2a-server-0.1.0.tgz oci://registry.quantum-forge.net/library
```

### Build Failures

```bash
# Clean Docker cache
docker system prune -a

# Rebuild without cache
docker build --no-cache -t a2a-server:latest .

# Check Dockerfile syntax
docker build --dry-run -t a2a-server:latest .
```

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Deploy to Quantum Forge

on:
  push:
    tags:
      - 'v*'

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Login to Quantum Forge
        run: |
          echo "${{ secrets.QUANTUM_FORGE_PASSWORD }}" | docker login registry.quantum-forge.net -u "${{ secrets.QUANTUM_FORGE_USERNAME }}" --password-stdin
          echo "${{ secrets.QUANTUM_FORGE_PASSWORD }}" | helm registry login registry.quantum-forge.net -u "${{ secrets.QUANTUM_FORGE_USERNAME }}" --password-stdin
      
      - name: Deploy to Quantum Forge
        run: |
          VERSION="${GITHUB_REF#refs/tags/}" ./deploy-to-quantum-forge.sh
```

---

## Next Steps

After deployment:

1. **Configure MCP for External Agents**: See [QUICK_REFERENCE_MCP_CONFIG.md](QUICK_REFERENCE_MCP_CONFIG.md)
2. **Set Up Monitoring**: Enable Prometheus metrics in Helm values
3. **Configure Ingress**: Add TLS/HTTPS for production
4. **Enable Autoscaling**: Configure HPA in Helm values

---

## Related Documentation

- [HELM_OCI_DEPLOYMENT.md](HELM_OCI_DEPLOYMENT.md) - General OCI deployment guide
- [MCP_AGENT_SYNC_SUMMARY.md](MCP_AGENT_SYNC_SUMMARY.md) - MCP agent synchronization
- [QUICK_REFERENCE_MCP_CONFIG.md](QUICK_REFERENCE_MCP_CONFIG.md) - MCP configuration
- [chart/README.md](chart/README.md) - Helm chart documentation

---

## Support

For issues with Quantum Forge deployment:
- Check registry status at your Quantum Forge portal
- Verify credentials and permissions
- Review logs: `docker logs` or `kubectl logs`
- GitHub Issues: https://github.com/rileyseaburg/A2A-Server-MCP/issues
