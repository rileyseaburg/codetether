# GitHub Actions Deployment Guide

Complete guide for using GitHub Actions to build and deploy the A2A Server to `acp.quantum-forge.net`.

## Overview

Two automated workflows:

1. **build-and-push.yml** - Builds Docker image and Helm chart on every push
2. **deploy-production.yml** - Deploys to production on manual trigger

## Quick Start

### 1. Configure Secrets

Set up required GitHub secrets (see [.github/SETUP_SECRETS.md](.github/SETUP_SECRETS.md)):

```bash
gh secret set QUANTUM_FORGE_USERNAME --body "your-username"
gh secret set QUANTUM_FORGE_PASSWORD --body "your-password"
cat ~/.kube/config | base64 | gh secret set KUBE_CONFIG
```

### 2. Push to Trigger Build

```bash
git add .
git commit -m "Deploy ACP server"
git push origin main
```

This automatically:
- ✅ Runs tests
- ✅ Builds Docker image
- ✅ Pushes to Quantum Forge registry
- ✅ Packages Helm chart
- ✅ Pushes chart to OCI registry

### 3. Deploy to Production

Go to **Actions** → **Deploy to Production** → **Run workflow**

Or via CLI:
```bash
gh workflow run deploy-production.yml \
  -f version=latest \
  -f skip_tests=false
```

## Workflows

### Build and Push Workflow

**File:** `.github/workflows/build-and-push.yml`

**Triggers:**
- Push to `main` or `develop` branches
- Push tags matching `v*` (e.g., `v1.0.0`)
- Pull requests to `main`
- Manual dispatch

**Jobs:**

1. **test** - Runs pytest with coverage
2. **build-and-push** - Builds and pushes Docker image
3. **package-and-push-helm** - Packages and pushes Helm chart
4. **deploy-notification** - Creates deployment summary

**Outputs:**
- Docker image pushed with multiple tags
- Helm chart pushed to OCI registry
- Deployment instructions in job summary

**Example Tags:**
```
registry.quantum-forge.net/library/a2a-server:latest
registry.quantum-forge.net/library/a2a-server:main
registry.quantum-forge.net/library/a2a-server:v1.0.0
registry.quantum-forge.net/library/a2a-server:main-sha-abc123
```

### Deploy Production Workflow

**File:** `.github/workflows/deploy-production.yml`

**Triggers:**
- Manual workflow dispatch only (for safety)

**Inputs:**
- `version` - Image version to deploy (default: `latest`)
- `skip_tests` - Skip pre-deployment tests (default: `false`)

**Jobs:**

1. **pre-deploy-tests** - Runs tests before deployment
2. **deploy** - Deploys to Kubernetes cluster

**What It Does:**
- Creates `a2a-system` namespace
- Generates production values file
- Deploys with Helm
- Verifies pods are running
- Gets LoadBalancer IP
- Creates deployment summary

**Environment:**
- Uses `production` GitHub Environment
- Requires manual approval (if configured)
- Sets environment URL to https://acp.quantum-forge.net

## Deployment Process

### Automated (Recommended)

```bash
# 1. Push code to trigger build
git push origin main

# 2. Wait for build to complete (check Actions tab)

# 3. Deploy to production
gh workflow run deploy-production.yml -f version=latest

# 4. Monitor deployment
gh run watch

# 5. Get LoadBalancer IP from job summary
# Configure DNS: acp.quantum-forge.net -> LoadBalancer IP
```

### Manual (Fallback)

If GitHub Actions fails, use local scripts:

```bash
# Build and push
docker login registry.quantum-forge.net
./deploy-acp.sh

# Or use PowerShell on Windows
.\deploy-acp.ps1 -Production
```

## Monitoring Deployments

### View Workflow Runs

**Web UI:**
- Go to **Actions** tab
- Click on workflow run
- View job details and logs

**CLI:**
```bash
# List recent runs
gh run list --workflow=build-and-push.yml

# Watch active run
gh run watch

# View run logs
gh run view --log
```

### Check Kubernetes Status

After deployment:

```bash
# Check pods
kubectl get pods -n a2a-system -w

# View logs
kubectl logs -n a2a-system -l app.kubernetes.io/name=a2a-server -f

# Get service IP
kubectl get svc -n a2a-system a2a-server

# Check ingress
kubectl get ingress -n a2a-system

# Verify certificate
kubectl get certificate -n a2a-system
```

### Access Services

Once deployed:

```bash
# Health check
curl https://acp.quantum-forge.net/health

# Agent card
curl https://acp.quantum-forge.net/.well-known/agent-card.json

# Monitoring UI
open https://acp.quantum-forge.net/v1/monitor/

# MCP tools
curl https://acp.quantum-forge.net:9000/mcp/v1/tools
```

## Version Management

### Semantic Versioning

Tag releases for production:

```bash
# Create version tag
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0

# This automatically builds with tags:
# - registry.quantum-forge.net/library/a2a-server:v1.0.0
# - registry.quantum-forge.net/library/a2a-server:1.0
# - registry.quantum-forge.net/library/a2a-server:1
# - registry.quantum-forge.net/library/a2a-server:latest
```

### Deploy Specific Version

```bash
# Deploy tagged version
gh workflow run deploy-production.yml -f version=v1.0.0

# Deploy branch build
gh workflow run deploy-production.yml -f version=main

# Deploy by commit SHA
gh workflow run deploy-production.yml -f version=main-sha-abc123
```

## Troubleshooting

### Build Failing

**Check workflow logs:**
```bash
gh run view --log
```

**Common issues:**
- Test failures → Fix tests and push again
- Docker build errors → Check Dockerfile syntax
- Registry auth errors → Verify secrets are set correctly

### Deployment Failing

**Check Kubernetes logs:**
```bash
kubectl describe pod -n a2a-system <pod-name>
kubectl logs -n a2a-system <pod-name>
```

**Common issues:**
- Image pull errors → Verify registry credentials
- Resource constraints → Check cluster resources
- Certificate issues → Check cert-manager logs

### Secrets Not Working

**Verify secrets are set:**
```bash
# List secrets (won't show values)
gh secret list

# Test credentials locally
echo "$QUANTUM_FORGE_PASSWORD" | docker login registry.quantum-forge.net \
  --username "$QUANTUM_FORGE_USERNAME" \
  --password-stdin
```

**Re-set secrets:**
```bash
gh secret set QUANTUM_FORGE_USERNAME
gh secret set QUANTUM_FORGE_PASSWORD
cat ~/.kube/config | base64 | gh secret set KUBE_CONFIG
```

## Rollback

### Rollback to Previous Version

```bash
# Via Helm
helm rollback a2a-server -n a2a-system

# To specific revision
helm rollback a2a-server 2 -n a2a-system

# View history
helm history a2a-server -n a2a-system
```

### Redeploy Previous Image

```bash
# Deploy older version
gh workflow run deploy-production.yml -f version=v1.0.0
```

## Production Best Practices

### 1. Use Protected Branches

```yaml
# In repository settings
- Require pull request reviews
- Require status checks to pass
- Require branches to be up to date
```

### 2. Environment Protection

```yaml
# In Settings → Environments → production
- Required reviewers: 1+
- Wait timer: 5 minutes
- Deployment branches: main only
```

### 3. Staged Rollouts

```bash
# Deploy to staging first
gh workflow run deploy-production.yml -f version=latest

# Test staging environment
curl https://staging.acp.quantum-forge.net/health

# Then deploy to production
# Update workflow to use different domain/namespace
```

### 4. Monitor Deployments

```bash
# Set up alerts
kubectl apply -f monitoring/alerts.yaml

# Watch metrics
kubectl top pods -n a2a-system

# Check logs continuously
kubectl logs -n a2a-system -l app.kubernetes.io/name=a2a-server -f | grep ERROR
```

## CI/CD Pipeline

```
┌─────────────┐
│  Git Push   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Run Tests  │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│Build Docker │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│Push Registry│
└──────┬──────┘
       │
       ▼
┌─────────────┐
│Package Helm │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Push OCI   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Manual    │
│   Trigger   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│Pre-Deploy   │
│   Tests     │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│Helm Deploy  │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Verify    │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Success   │
└─────────────┘
```

## Additional Resources

- **Setup Guide:** [.github/SETUP_SECRETS.md](.github/SETUP_SECRETS.md)
- **Deployment Guide:** [ACP_DEPLOYMENT.md](ACP_DEPLOYMENT.md)
- **Quick Start:** [QUICKSTART_ACP.md](QUICKSTART_ACP.md)
- **Helm Chart:** [chart/README.md](chart/README.md)
- **Monitoring:** [ui/README.md](ui/README.md)

## Support

**GitHub Actions Issues:**
- Check workflow status: https://github.com/rileyseaburg/A2A-Server-MCP/actions
- View logs: Click on failed job → View logs
- Re-run: Click "Re-run jobs" button

**Kubernetes Issues:**
```bash
kubectl describe deployment a2a-server -n a2a-system
kubectl get events -n a2a-system --sort-by='.lastTimestamp'
```

**Registry Issues:**
- Verify credentials with registry admin
- Check quota/storage limits
- Test push/pull manually
