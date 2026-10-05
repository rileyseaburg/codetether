# Quick Guide: GitHub Actions Deployment

## Setup (One-Time)

### 1. Set GitHub Secrets

```bash
# Set Quantum Forge credentials
gh secret set QUANTUM_FORGE_USERNAME
# Enter your username when prompted

gh secret set QUANTUM_FORGE_PASSWORD
# Enter your password when prompted

# Set Kubernetes config
cat ~/.kube/config | base64 | gh secret set KUBE_CONFIG
```

**Or via GitHub Web UI:**
1. Go to Settings → Secrets and variables → Actions
2. Click "New repository secret"
3. Add: `QUANTUM_FORGE_USERNAME`, `QUANTUM_FORGE_PASSWORD`, `KUBE_CONFIG`

See [.github/SETUP_SECRETS.md](.github/SETUP_SECRETS.md) for detailed instructions.

---

## Deploy Process

### Step 1: Push Code (Automatic Build)

```bash
git add .
git commit -m "Deploy to acp.quantum-forge.net"
git push origin main
```

**This automatically:**
- ✅ Runs tests
- ✅ Builds Docker image → `registry.quantum-forge.net/library/a2a-server:latest`
- ✅ Pushes to registry
- ✅ Packages Helm chart → `oci://registry.quantum-forge.net/library/a2a-server:0.1.0`
- ✅ Displays deployment instructions

### Step 2: Deploy to Production (Manual Trigger)

**Via GitHub Web UI:**
1. Go to **Actions** tab
2. Click **Deploy to Production (acp.quantum-forge.net)**
3. Click **Run workflow**
4. Select branch: `main`
5. Enter version: `latest` (or specific version like `v1.0.0`)
6. Click **Run workflow**

**Via GitHub CLI:**
```bash
gh workflow run deploy-production.yml -f version=latest -f skip_tests=false
```

### Step 3: Monitor Deployment

**Watch workflow:**
```bash
gh run watch
```

**Check Kubernetes:**
```bash
kubectl get pods -n a2a-system -w
kubectl get svc -n a2a-system a2a-server
```

### Step 4: Configure DNS

Get LoadBalancer IP from workflow summary or:
```bash
kubectl get svc -n a2a-system a2a-server -o jsonpath='{.status.loadBalancer.ingress[0].ip}'
```

Configure DNS A record:
```
acp.quantum-forge.net → <EXTERNAL-IP>
```

### Step 5: Verify

```bash
# Wait for TLS (2-5 minutes)
kubectl get certificate -n a2a-system

# Test endpoints
curl https://acp.quantum-forge.net/health
curl https://acp.quantum-forge.net/.well-known/agent-card.json

# Open monitoring UI
open https://acp.quantum-forge.net/v1/monitor/
```

---

## Available Workflows

### 1. Build and Push
- **File:** `.github/workflows/build-and-push.yml`
- **Triggers:** Push to main, tags, PRs
- **Purpose:** Build and push Docker + Helm automatically

### 2. Deploy Production
- **File:** `.github/workflows/deploy-production.yml`
- **Triggers:** Manual only
- **Purpose:** Deploy to Kubernetes cluster

---

## Version Management

### Deploy Latest

```bash
gh workflow run deploy-production.yml -f version=latest
```

### Deploy Specific Version

```bash
# Create tag
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0

# Wait for build to complete

# Deploy tagged version
gh workflow run deploy-production.yml -f version=v1.0.0
```

### Deploy Branch Build

```bash
gh workflow run deploy-production.yml -f version=main
```

---

## Quick Commands

```bash
# View workflow runs
gh run list

# Watch current run
gh run watch

# View logs
gh run view --log

# Re-run failed workflow
gh run rerun <run-id>

# Check pod status
kubectl get pods -n a2a-system

# View logs
kubectl logs -n a2a-system -l app.kubernetes.io/name=a2a-server -f

# Get service IP
kubectl get svc -n a2a-system a2a-server

# Rollback
helm rollback a2a-server -n a2a-system
```

---

## Troubleshooting

### Build Fails
- Check Actions logs: Actions → workflow run → job
- Fix errors and push again

### Deployment Fails
- Check secrets are set: Settings → Secrets
- Verify kubectl access: `kubectl get nodes`
- Check pod status: `kubectl describe pod -n a2a-system <pod-name>`

### Services Not Accessible
- Check DNS is configured
- Verify certificate issued: `kubectl get certificate -n a2a-system`
- Check ingress: `kubectl get ingress -n a2a-system`

---

## Production Endpoints

After successful deployment:

- 🌐 **Monitoring UI:** https://acp.quantum-forge.net/v1/monitor/
- 📡 **Agent Card:** https://acp.quantum-forge.net/.well-known/agent-card.json
- 🔧 **MCP Tools:** https://acp.quantum-forge.net:9000/mcp/v1/tools
- ❤️ **Health:** https://acp.quantum-forge.net/health

---

## Full Documentation

- **Complete Guide:** [GITHUB_ACTIONS_DEPLOYMENT.md](GITHUB_ACTIONS_DEPLOYMENT.md)
- **Secrets Setup:** [.github/SETUP_SECRETS.md](.github/SETUP_SECRETS.md)
- **Deployment Guide:** [ACP_DEPLOYMENT.md](ACP_DEPLOYMENT.md)
- **Quick Start:** [QUICKSTART_ACP.md](QUICKSTART_ACP.md)
