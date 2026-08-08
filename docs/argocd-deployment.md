# ArgoCD Deployment Runbook

This repo deploys CodeTether to Kubernetes through Argo CD using the
**app-of-apps** pattern. The `deploy/argocd/` directory contains all ArgoCD
Application and AppProject manifests, managed via Kustomize.

## Files

| File | Purpose |
|------|---------|
| `deploy/argocd/project.yaml` | AppProject `codetether` — source repos, destinations, RBAC |
| `deploy/argocd/external-secrets-operator.yaml` | ESO helm chart (sync-wave **-10** — deployed first) |
| `deploy/argocd/secrets.yaml` | Vault → Kubernetes secret sync (`deploy/secrets/`) |
| `deploy/argocd/application.yaml` | A2A server Helm chart with production values |
| `deploy/argocd/marketing.yaml` | Marketing site Helm chart |
| `deploy/argocd/kustomization.yaml` | Resource ordering for `kubectl apply -k` |
| `scripts/bootstrap-argocd.sh` | Full lifecycle CLI: bootstrap, verify, upgrade, recovery, dry-run |
| `scripts/argocd-render-check.sh` | CI-friendly static manifest validation |

## Bootstrap Ordering

The applications deploy in this order (controlled by `sync-wave` annotations
and the script's sync loop):

| Wave | Application | Why First |
|------|------------|-----------|
| -10 | `external-secrets-operator` | CRDs must exist before ExternalSecret resources |
| 0 | `codetether-secrets` | Vault → K8s secrets must exist before workloads start |
| 0 | `codetether-a2a-server` | Main API server |
| 0 | `codetether-marketing` | Marketing site (depends on a2a-server internally) |

---

## Normal Bootstrap

**One command to bootstrap everything:**

```bash
make argocd-bootstrap
# or: ./scripts/bootstrap-argocd.sh bootstrap
```

What this does:
1. Creates the `argocd` namespace (idempotent)
2. Installs Argo CD stable if not already present
3. Waits for `argocd-server` to be available
4. Runs image-tag safety checks
5. Applies `deploy/argocd` via Kustomize
6. Waits for ESO CRDs to establish
7. Applies `deploy/secrets` (Vault-backed ExternalSecrets)
8. Syncs each application in dependency order
9. Waits for all apps to reach `Synced + Healthy`
10. Captures evidence artifacts to `artifacts/argocd-evidence/<timestamp>/`

### Prerequisites

- Kubernetes context points at the target cluster
- Argo CD can read this repo (SSH repo URL configured)
- Runtime secrets exist in HashiCorp Vault KV v2
- Vault Kubernetes auth role `codetether-a2a-server-secret-sync` is configured

```bash
# Add repository credentials (if private)
argocd repo add git@github.com:rileyseaburg/codetether.git \
  --ssh-private-key-path ~/.ssh/id_ed25519
```

### Verify After Bootstrap

```bash
make argocd-verify
# Captures: sync status, health, revision, operation phase, managed resources, rollout
# Evidence saved to artifacts/argocd-evidence/<timestamp>/
```

---

## Upgrade Flow

When promoting a new image tag to production:

```bash
# 1. Update the image tag in the Application manifest
yq -i '.spec.source.helm.valuesObject.image.tag = "NEW-TAG"' deploy/argocd/application.yaml
yq -i '.spec.source.helm.valuesObject.blueGreen.rolloutId.green = "NEW-TAG"' deploy/argocd/application.yaml

# 2. Commit and push
git add deploy/argocd/application.yaml
git commit -m "Deploy CodeTether NEW-TAG via Argo CD"
git push

# 3. Run upgrade with safety checks
make argocd-upgrade
```

What `argocd-upgrade` does:
1. Captures pre-upgrade evidence
2. Compares desired image tags to current live tags (safety guard)
3. Server-side dry-run validation
4. Applies manifests
5. Refreshes and syncs each app in order
6. Captures post-upgrade evidence

### Safety Checks

The upgrade command guards against:
- **Stale image tags**: Warns if desired tag matches live tag (no-op)
- **`latest` tag**: Hard-fails — nondeterministic deploys are unsafe
- **Missing fields**: Validates Application specs have required fields

Set `SKIP_SAFETY_CHECK=1` to bypass guards (not recommended for production).

---

## Rollback Flow

### GitOps Rollback (Preferred)

Argo CD is the source of truth. To roll back:

```bash
# 1. Revert the commit that changed the image tag
git revert HEAD
git push

# 2. Argo CD will auto-sync if automated sync is enabled
# 3. Or manually sync:
make argocd-upgrade
```

### Blue-Green Slot Rollback

If using blue-green deployment and the new slot is unhealthy:

```bash
# Switch traffic back to the previous slot
yq -i '.spec.source.helm.valuesObject.blueGreen.serviceColor = "blue"' deploy/argocd/application.yaml
git commit -am "Rollback: switch to blue slot"
git push
make argocd-upgrade
```

### Emergency Rollback via Helm

If Argo CD itself is broken:

```bash
helm rollback a2a-server -n a2a-system
```

---

## Emergency Recovery

**One command to diagnose and recover:**

```bash
make argocd-recovery
# or: ./scripts/bootstrap-argocd.sh recovery
```

This diagnoses:
- **Stuck operations**: Detects running operations that have timed out
- **OutOfSync**: Identifies drift between Git and cluster state
- **SyncFailed**: Shows failed sync operations with root cause hints
- **Degraded health**: Shows pod status, events, and log hints
- **Missing resources**: Identifies apps that haven't been created yet
- **Orphaned resources**: Detects unmanaged resources in app namespaces

### Common Recovery Scenarios

#### Stuck Sync

```bash
# 1. Check what's stuck
argocd app get codetether-a2a-server --show-operation

# 2. Terminate the stuck operation
argocd app terminate-op codetether-a2a-server

# 3. Re-sync
argocd app sync codetether-a2a-server
```

#### Image Pull Error

```bash
# 1. Check pod status
kubectl describe pods -n a2a-system -l app.kubernetes.io/name=a2a-server

# 2. Verify the image tag exists in the registry
gcloud artifacts docker images list \
  us-central1-docker.pkg.dev/spotlessbinco/codetether/a2a-server-mcp \
  --include-tags

# 3. Verify the pull secret
kubectl get secret gcp-artifact-registry -n a2a-system -o jsonpath='{.data}' | jq
```

#### Secret Not Synced

```bash
# 1. Check ExternalSecret status
kubectl get externalsecret -n a2a-system

# 2. Check Vault connectivity
kubectl logs -n external-secrets -l app.kubernetes.io/name=external-secrets

# 3. Force re-sync
kubectl annotate externalsecret -n a2a-system --all \
  force-sync="$(date +%s)" --overwrite
```

#### Orphaned Resources

```bash
# 1. List orphaned resources detected by Argo CD
argocd app get codetether-a2a-server --orphaned

# 2. If they should be managed, add them to the Helm chart
# 3. If genuinely orphaned, prune them:
argocd app sync codetether-a2a-server --prune
```

#### Nuclear Option: Full Re-bootstrap

```bash
make argocd-bootstrap
```

This re-applies all manifests from scratch. It's safe because Argo CD uses
server-side apply and prune-last.

---

## Evidence Artifacts

Every bootstrap, verify, upgrade, and recovery command captures durable evidence
to `artifacts/argocd-evidence/<timestamp>/`:

| File | Contents |
|------|----------|
| `<app>.json` | Sync status, health, revision, operation phase, managed resource count |
| `<app>-resources.json` | Per-resource status and health |
| `<app>-rollout.txt` | Deployment, ReplicaSet, and pod status |
| `apps-overview.txt` | `kubectl get applications` wide output |

These artifacts are suitable for audit trails and compliance evidence.

---

## Pre-flight Validation

### Static Render Check (CI-friendly, no cluster needed)

```bash
make argocd-render-check
```

Validates:
- Kustomize render succeeds
- Required kinds present (AppProject, Application)
- Each Application has required spec fields (project, destination, source)
- Sync-wave annotations are present
- YAML is parseable

### Server-side Dry-run (requires cluster access)

```bash
make argocd-dry-run
```

Validates all of the above plus:
- Kubernetes API server accepts the manifests
- No admission webhook rejections

---

## Make Targets Quick Reference

| Target | Description |
|--------|-------------|
| `make argocd-bootstrap` | Full bootstrap: install ArgoCD, apply, sync, wait |
| `make argocd-verify` | Capture evidence without changes |
| `make argocd-upgrade` | Apply with image-tag safety checks |
| `make argocd-recovery` | Diagnose issues, print GitOps-first next steps |
| `make argocd-dry-run` | Server-side dry-run validation |
| `make argocd-render-check` | CI-friendly static validation |

---

## Vault Secret Setup

Before syncing `codetether-a2a-server`, these Vault KV v2 paths must exist:

```bash
vault kv put secret/codetether/a2a-server/database \
  DATABASE_URL='postgresql://USER:PASSWORD@HOST:5432/a2a_server'

vault kv put secret/codetether/a2a-server/auth \
  A2A_AUTH_TOKENS='worker:TOKEN,admin:TOKEN'

DOCKER_CONFIG_JSON="$(kubectl create secret docker-registry gcp-artifact-registry \
  --dry-run=client -o json \
  --docker-server=us-central1-docker.pkg.dev \
  --docker-username=_json_key \
  --docker-password="$(cat /path/to/gcp-service-account.json)" \
  | jq -r '.data[".dockerconfigjson"]' | base64 -d)"

vault kv put secret/codetether/a2a-server/artifact-registry \
  .dockerconfigjson="$DOCKER_CONFIG_JSON"
```

Confirm ESO has synced:

```bash
kubectl wait externalsecret -n a2a-system \
  a2a-server-database a2a-server-auth-tokens gcp-artifact-registry \
  --for=condition=Ready --timeout=180s
```

---

## Automated Sync

After the first successful manual sync, automated sync is enabled in the
Application manifests:

```yaml
syncPolicy:
  automated:
    prune: true
    selfHeal: true
```

This means Argo CD will automatically sync when Git state changes. The
bootstrap/upgrade commands are still useful for controlled rollouts with
evidence capture and safety checks.
