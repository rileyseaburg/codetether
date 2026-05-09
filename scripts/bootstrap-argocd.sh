#!/usr/bin/env bash
set -euo pipefail

ARGOCD_NAMESPACE="${ARGOCD_NAMESPACE:-argocd}"
BOOTSTRAP_DIR="${BOOTSTRAP_DIR:-deploy/argocd}"
SECRET_SYNC_DIR="${SECRET_SYNC_DIR:-deploy/secrets}"

kubectl create namespace "${ARGOCD_NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -

if ! kubectl get deployment argocd-server -n "${ARGOCD_NAMESPACE}" >/dev/null 2>&1; then
  kubectl apply -n "${ARGOCD_NAMESPACE}" \
    -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
fi

kubectl wait --for=condition=Available deployment/argocd-server \
  -n "${ARGOCD_NAMESPACE}" \
  --timeout=300s

kubectl apply -k "${BOOTSTRAP_DIR}"

if kubectl get application external-secrets-operator -n "${ARGOCD_NAMESPACE}" >/dev/null 2>&1; then
  kubectl wait --for=condition=Established \
    crd/externalsecrets.external-secrets.io \
    crd/secretstores.external-secrets.io \
    --timeout=300s

  kubectl apply -k "${SECRET_SYNC_DIR}"
fi

cat <<'EOF'
Argo CD bootstrap manifests applied.

Before syncing codetether-a2a-server, make sure these Vault KV v2 paths exist:
  - secret/codetether/a2a-server/database: DATABASE_URL
  - secret/codetether/a2a-server/auth: A2A_AUTH_TOKENS
  - secret/codetether/a2a-server/artifact-registry: .dockerconfigjson

Then confirm ESO has synced the Kubernetes secrets:
  kubectl wait externalsecret -n a2a-system \
    a2a-server-database a2a-server-auth-tokens gcp-artifact-registry \
    --for=condition=Ready --timeout=180s

Then sync:
  argocd app sync codetether-a2a-server
  argocd app wait codetether-a2a-server --sync --health --timeout 600
EOF
