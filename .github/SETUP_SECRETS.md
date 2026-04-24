# GitHub Actions Secrets Setup

To use the GitHub Actions workflows for building images, publishing Helm charts, and deploying to Kubernetes, configure the following secrets.

## Required Secrets

### 1. Google Artifact Registry Credentials

**`GCP_SA_KEY`**
- JSON key for a Google Cloud service account with permission to push to `us-central1-docker.pkg.dev/spotlessbinco/codetether`
- Used for: Docker and Helm registry authentication

### 2. Kubernetes Configuration

**`KUBE_CONFIG`**
- Base64-encoded Kubernetes config file
- Used for: Deploying to Kubernetes cluster

## How to Set Secrets

### Via GitHub Web UI

1. Go to your repository on GitHub
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add each secret with the name and value

### Via GitHub CLI

```bash
# Set Google Artifact Registry credentials
gh secret set GCP_SA_KEY < service-account-key.json

# Set Kubernetes config (base64 encoded)
cat ~/.kube/config | base64 | gh secret set KUBE_CONFIG
```

## Generating Kubernetes Config

If you need to create a service account for GitHub Actions:

```bash
# Create service account
kubectl create serviceaccount github-deployer -n a2a-system

# Create cluster role binding
kubectl create clusterrolebinding github-deployer \
  --clusterrole=cluster-admin \
  --serviceaccount=a2a-system:github-deployer

# Get token (Kubernetes 1.24+)
kubectl create token github-deployer -n a2a-system --duration=87600h > github-token.txt

# Create kubeconfig
cat > github-kubeconfig.yaml <<EOF
apiVersion: v1
kind: Config
clusters:
- cluster:
    certificate-authority-data: $(kubectl config view --raw -o jsonpath='{.clusters[0].cluster.certificate-authority-data}')
    server: $(kubectl config view --raw -o jsonpath='{.clusters[0].cluster.server}')
  name: kubernetes
contexts:
- context:
    cluster: kubernetes
    user: github-deployer
    namespace: a2a-system
  name: github-deployer@kubernetes
current-context: github-deployer@kubernetes
users:
- name: github-deployer
  user:
    token: $(cat github-token.txt)
EOF

# Base64 encode and set secret
cat github-kubeconfig.yaml | base64 | gh secret set KUBE_CONFIG

# Clean up
rm github-token.txt github-kubeconfig.yaml
```

## Environment Setup (Optional)

For production deployments, you can create a GitHub Environment:

1. Go to **Settings** → **Environments**
2. Click **New environment**
3. Name it `production`
4. Add protection rules:
   - ✅ Required reviewers (optional)
   - ✅ Wait timer (optional)
5. Add environment-specific secrets if needed

## Testing Credentials

Test that your secrets work:

```bash
# Test Docker login using local gcloud auth
gcloud auth configure-docker us-central1-docker.pkg.dev --quiet
docker pull us-central1-docker.pkg.dev/spotlessbinco/codetether/codetether-marketing:latest

# Test Helm login using local gcloud auth
gcloud auth print-access-token | helm registry login https://us-central1-docker.pkg.dev \
  --username oauth2accesstoken \
  --password-stdin

# Test kubectl access
export KUBECONFIG=/tmp/test-kubeconfig
echo "$KUBE_CONFIG" | base64 -d > $KUBECONFIG
kubectl get nodes
kubectl get pods -n a2a-system
```

## Security Best Practices

1. **Prefer Workload Identity Federation** over long-lived JSON keys when practical
2. **Limit service account scope** to only what's needed for Artifact Registry and deployment
3. **Rotate credentials regularly** (every 90 days recommended)
4. **Use environment protection** for production deployments
5. **Monitor secret usage** in Actions logs
6. **Never commit secrets** to the repository

## Workflow Permissions

The workflows need these permissions:

- **contents: read** - To checkout code
- **id-token: write** - To mint Google Cloud access tokens
- **packages: write** - To push Docker images and Helm charts

These are configured in the workflow files.

## Troubleshooting

### "authentication required" error
- Verify `GCP_SA_KEY` is set to valid service account JSON
- Check if the service account key is expired or disabled
- Ensure the service account has push access to the Artifact Registry repository

### "unauthorized" error in Kubernetes
- Verify `KUBE_CONFIG` is base64-encoded correctly
- Check service account has sufficient permissions
- Ensure token hasn't expired

### Secrets not available in workflow
- Check secret names match exactly (case-sensitive)
- Verify secrets are set at repository or organization level
- For environments, ensure environment name matches workflow

## Support

For issues with GitHub Actions:
- Check workflow logs: Actions → workflow run → job → step
- Verify secrets: Settings → Secrets and variables → Actions
- Test credentials locally first

For Quantum Forge registry issues:
- Contact registry administrator
- Verify account access and permissions
