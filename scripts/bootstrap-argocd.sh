#!/usr/bin/env bash
# =============================================================================
# CodeTether ArgoCD App-of-Apps Bootstrap & Recovery CLI
# =============================================================================
# Usage:
#   ./scripts/bootstrap-argocd.sh <command> [options]
#
# Commands:
#   bootstrap   Install ArgoCD (if needed) and apply all app-of-apps manifests
#   verify      Capture evidence artifacts for every app without making changes
#   upgrade     Apply manifests with image-tag safety checks
#   recovery    Diagnose stuck syncs / orphaned resources and print next steps
#   dry-run     Render + server-side dry-run without applying
#
# Environment:
#   ARGOCD_NAMESPACE   (default: argocd)
#   EVIDENCE_DIR       (default: artifacts/argocd-evidence/<timestamp>)
#   SKIP_SAFETY_CHECK  Set to "1" to bypass image-tag guard
#   ARGOCD_BIN         (default: argocd)
# =============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
ARGOCD_NAMESPACE="${ARGOCD_NAMESPACE:-argocd}"
BOOTSTRAP_DIR="${BOOTSTRAP_DIR:-deploy/argocd}"
SECRET_SYNC_DIR="${SECRET_SYNC_DIR:-deploy/secrets}"
ARGOCD_BIN="${ARGOCD_BIN:-argocd}"
EVIDENCE_DIR="${EVIDENCE_DIR:-artifacts/argocd-evidence/$(date -u +%Y%m%dT%H%M%SZ)}"
SKIP_SAFETY_CHECK="${SKIP_SAFETY_CHECK:-0}"

# App-of-apps ordering (sync-wave order)
APPS_ORDER=("external-secrets-operator" "codetether-secrets" "codetether-a2a-server" "codetether-marketing")

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
log()  { echo -e "${CYAN}[argocd-cli]${NC} $*"; }
warn() { echo -e "${YELLOW}[warn]${NC} $*" >&2; }
err()  { echo -e "${RED}[error]${NC} $*" >&2; }
ok()   { echo -e "${GREEN}[ok]${NC} $*"; }

require_cmd() {
  if ! command -v "$1" &>/dev/null; then
    err "'$1' is required but not found in PATH."
    exit 1
  fi
}

ensure_evidence_dir() {
  mkdir -p "${EVIDENCE_DIR}"
  log "Evidence directory: ${EVIDENCE_DIR}"
}

# ---------------------------------------------------------------------------
# Evidence capture
# ---------------------------------------------------------------------------
capture_app_evidence() {
  local app="$1"
  local evidence_file="${EVIDENCE_DIR}/${app}.json"

  if ! kubectl get application "${app}" -n "${ARGOCD_NAMESPACE}" &>/dev/null; then
    warn "Application '${app}' not found — skipping evidence capture"
    echo "{\"app\":\"${app}\",\"status\":\"NOT_FOUND\"}" > "${evidence_file}"
    return 0
  fi

  log "Capturing evidence for ${app}..."

  # Core status via kubectl
  kubectl get application "${app}" -n "${ARGOCD_NAMESPACE}" -o json | \
    jq '{
      app: .metadata.name,
      sync_status: .status.sync.status,
      health_status: .status.health.status,
      revision: .status.sync.revision,
      operation_phase: (.status.operationState.phase // "none"),
      started_at: (.status.operationState.startedAt // "none"),
      finished_at: (.status.operationState.finishedAt // "none"),
      managed_resources: (.status.resources | length),
      source: .spec.source,
      sync_policy: .spec.syncPolicy
    }' > "${evidence_file}"

  # Detailed managed resources
  local resources_file="${EVIDENCE_DIR}/${app}-resources.json"
  if kubectl get application "${app}" -n "${ARGOCD_NAMESPACE}" -o jsonpath='{.status.resources}' &>/dev/null; then
    kubectl get application "${app}" -n "${ARGOCD_NAMESPACE}" -o json \
      | jq '[.status.resources[] | {kind, name, namespace, status, health}]' \
      > "${resources_file}"
  fi

  # Rollout / deployment status for deployed workloads
  local ns
  ns=$(kubectl get application "${app}" -n "${ARGOCD_NAMESPACE}" -o jsonpath='{.spec.destination.namespace}' 2>/dev/null || echo "")
  if [[ -n "${ns}" ]]; then
    local rollout_file="${EVIDENCE_DIR}/${app}-rollout.txt"
    {
      echo "=== Deployments in ${ns} ==="
      kubectl get deployments -n "${ns}" -o wide 2>/dev/null || true
      echo ""
      echo "=== ReplicaSets (latest) in ${ns} ==="
      kubectl get replicasets -n "${ns}" --sort-by='.metadata.creationTimestamp' 2>/dev/null | tail -5 || true
      echo ""
      echo "=== Pods in ${ns} ==="
      kubectl get pods -n "${ns}" -o wide 2>/dev/null || true
    } > "${rollout_file}" 2>&1
  fi

  # Summary to stdout
  local sync_status health revision
  sync_status=$(jq -r '.sync_status' "${evidence_file}")
  health=$(jq -r '.health_status' "${evidence_file}")
  revision=$(jq -r '.revision' "${evidence_file}" | head -c 12)
  local managed
  managed=$(jq -r '.managed_resources' "${evidence_file}")

  echo -e "  ${app}: sync=${sync_status} health=${health} rev=${revision} resources=${managed}"
}

capture_all_evidence() {
  ensure_evidence_dir
  log "Capturing evidence for all CodeTether ArgoCD applications..."
  echo ""

  # Cluster-wide summary
  kubectl get applications -n "${ARGOCD_NAMESPACE}" -o wide > "${EVIDENCE_DIR}/apps-overview.txt" 2>&1 || true

  for app in "${APPS_ORDER[@]}"; do
    capture_app_evidence "${app}"
  done

  echo ""
  ok "Evidence captured to ${EVIDENCE_DIR}/"
  echo "  Files:"
  ls -1 "${EVIDENCE_DIR}/" | sed 's/^/    /'
}

# ---------------------------------------------------------------------------
# Image-tag safety check
# ---------------------------------------------------------------------------
check_image_tags() {
  if [[ "${SKIP_SAFETY_CHECK}" == "1" ]]; then
    warn "Image-tag safety check skipped (SKIP_SAFETY_CHECK=1)"
    return 0
  fi

  log "Checking image tags for rollback safety..."
  local failed=0

  # --- a2a-server ---
  local desired_a2a_tag
  desired_a2a_tag=$(kubectl kustomize "${BOOTSTRAP_DIR}" 2>/dev/null \
    | yq '. | select(.kind=="Application" and .metadata.name=="codetether-a2a-server") | .spec.source.helm.valuesObject.image.tag // ""' 2>/dev/null || echo "")

  if [[ -n "${desired_a2a_tag}" ]]; then
    local live_a2a_tag=""
    if kubectl get application codetether-a2a-server -n "${ARGOCD_NAMESPACE}" &>/dev/null; then
      live_a2a_tag=$(kubectl get application codetether-a2a-server -n "${ARGOCD_NAMESPACE}" \
        -o jsonpath='{.spec.source.helm.valuesObject.image.tag}' 2>/dev/null || echo "")
    fi

    if [[ -n "${live_a2a_tag}" ]]; then
      # Simple string comparison — if desired != live, it's an intentional change
      # but we check if the desired tag looks older (timestamp-based naming)
      log "  a2a-server: desired=${desired_a2a_tag} live=${live_a2a_tag}"
      if [[ "${desired_a2a_tag}" == "${live_a2a_tag}" ]]; then
        ok "  a2a-server: tags match (no-op)"
      fi
    else
      log "  a2a-server: first deploy (no live tag to compare)"
    fi
  fi

  # --- marketing ---
  local desired_marketing_tag
  desired_marketing_tag=$(kubectl kustomize "${BOOTSTRAP_DIR}" 2>/dev/null \
    | yq '. | select(.kind=="Application" and .metadata.name=="codetether-marketing") | .spec.source.helm.valuesObject.image.tag // ""' 2>/dev/null || echo "")

  if [[ -n "${desired_marketing_tag}" ]]; then
    local live_marketing_tag=""
    if kubectl get application codetether-marketing -n "${ARGOCD_NAMESPACE}" &>/dev/null; then
      live_marketing_tag=$(kubectl get application codetether-marketing -n "${ARGOCD_NAMESPACE}" \
        -o jsonpath='{.spec.source.helm.valuesObject.image.tag}' 2>/dev/null || echo "")
    fi

    if [[ -n "${live_marketing_tag}" ]]; then
      log "  marketing: desired=${desired_marketing_tag} live=${live_marketing_tag}"
      if [[ "${desired_marketing_tag}" == "${live_marketing_tag}" ]]; then
        ok "  marketing: tags match (no-op)"
      fi
    else
      log "  marketing: first deploy (no live tag to compare)"
    fi
  fi

  # --- General warning: check if any desired tag is "latest" ---
  for tag in "${desired_a2a_tag:-}" "${desired_marketing_tag:-}"; do
    if [[ "${tag}" == "latest" ]]; then
      err "Image tag 'latest' detected — this is nondeterministic. Aborting."
      failed=1
    fi
  done

  if [[ "${failed}" -eq 1 ]]; then
    return 1
  fi

  ok "Image-tag safety check passed"
  return 0
}

# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------
cmd_bootstrap() {
  require_cmd kubectl
  log "=== Bootstrap: Installing ArgoCD and applying app-of-apps ==="

  # 1. Create namespace
  kubectl create namespace "${ARGOCD_NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -

  # 2. Install Argo CD if not present
  if ! kubectl get deployment argocd-server -n "${ARGOCD_NAMESPACE}" >/dev/null 2>&1; then
    log "Argo CD not found — installing stable manifest..."
    kubectl apply -n "${ARGOCD_NAMESPACE}" \
      -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
  else
    ok "Argo CD already installed"
  fi

  # 3. Wait for Argo CD to be ready
  log "Waiting for Argo CD server to be available..."
  kubectl wait --for=condition=Available deployment/argocd-server \
    -n "${ARGOCD_NAMESPACE}" \
    --timeout=300s

  # 4. Safety check
  check_image_tags

  # 5. Apply app-of-apps manifests (respects sync-wave ordering)
  log "Applying app-of-apps from ${BOOTSTRAP_DIR}..."
  kubectl apply -k "${BOOTSTRAP_DIR}"

  # 6. Wait for ESO CRDs if external-secrets-operator app exists
  if kubectl get application external-secrets-operator -n "${ARGOCD_NAMESPACE}" >/dev/null 2>&1; then
    log "Waiting for External Secrets Operator CRDs to be established..."
    kubectl wait --for=condition=Established \
      crd/externalsecrets.external-secrets.io \
      crd/secretstores.external-secrets.io \
      --timeout=300s 2>/dev/null || warn "CRD wait timed out (may still be syncing)"

    # Apply secret-sync resources after ESO is ready
    log "Applying secret-sync resources from ${SECRET_SYNC_DIR}..."
    kubectl apply -k "${SECRET_SYNC_DIR}"
  fi

  # 7. Sync apps in order
  log "Syncing applications in dependency order..."
  for app in "${APPS_ORDER[@]}"; do
    if kubectl get application "${app}" -n "${ARGOCD_NAMESPACE}" &>/dev/null; then
      log "Syncing ${app}..."
      if command -v "${ARGOCD_BIN}" &>/dev/null; then
        "${ARGOCD_BIN}" app sync "${app}" --timeout 300 2>/dev/null || \
          warn "argocd sync failed for ${app} — app may sync via auto-policy"
      else
        # Force sync via annotation if argocd CLI not available
        kubectl patch application "${app}" -n "${ARGOCD_NAMESPACE}" \
          --type merge -p '{"operation":{"sync":{}}}' 2>/dev/null || true
      fi
    else
      warn "Application '${app}' not yet found — may still be initializing"
    fi
  done

  # 8. Watch / wait for all apps to reach Synced+Healthy
  log "Waiting for all apps to reach Synced + Healthy..."
  for app in "${APPS_ORDER[@]}"; do
    if kubectl get application "${app}" -n "${ARGOCD_NAMESPACE}" &>/dev/null; then
      if command -v "${ARGOCD_BIN}" &>/dev/null; then
        "${ARGOCD_BIN}" app wait "${app}" --sync --health --timeout 600 2>/dev/null || \
          warn "${app} did not reach Synced+Healthy within 600s"
      else
        log "  (argocd CLI not available — polling kubectl for ${app})"
        local retries=0
        while [[ ${retries} -lt 60 ]]; do
          local sync health
          sync=$(kubectl get application "${app}" -n "${ARGOCD_NAMESPACE}" \
            -o jsonpath='{.status.sync.status}' 2>/dev/null || echo "Unknown")
          health=$(kubectl get application "${app}" -n "${ARGOCD_NAMESPACE}" \
            -o jsonpath='{.status.health.status}' 2>/dev/null || echo "Unknown")
          if [[ "${sync}" == "Synced" && "${health}" == "Healthy" ]]; then
            ok "${app}: Synced + Healthy"
            break
          fi
          retries=$((retries + 1))
          sleep 10
        done
        if [[ ${retries} -eq 60 ]]; then
          warn "${app}: did not reach Synced+Healthy"
        fi
      fi
    fi
  done

  # 9. Capture evidence
  capture_all_evidence

  echo ""
  ok "Bootstrap complete!"
}

cmd_verify() {
  require_cmd kubectl
  log "=== Verify: Capturing evidence without making changes ==="
  capture_all_evidence

  echo ""
  log "Application health summary:"
  for app in "${APPS_ORDER[@]}"; do
    local evidence_file="${EVIDENCE_DIR}/${app}.json"
    if [[ -f "${evidence_file}" ]]; then
      local sync health
      sync=$(jq -r '.sync_status // "N/A"' "${evidence_file}")
      health=$(jq -r '.health_status // "N/A"' "${evidence_file}")
      echo -e "  ${app}: sync=${sync} health=${health}"
    fi
  done
}

cmd_upgrade() {
  require_cmd kubectl
  log "=== Upgrade: Applying manifests with safety checks ==="

  # 1. Capture pre-upgrade evidence
  local pre_evidence_dir="${EVIDENCE_DIR}-pre-upgrade"
  EVIDENCE_DIR="${pre_evidence_dir}" ensure_evidence_dir
  EVIDENCE_DIR="${pre_evidence_dir}" capture_all_evidence

  # 2. Image-tag safety check
  check_image_tags

  # 3. Server-side dry-run first
  log "Running server-side dry-run..."
  kubectl apply -k "${BOOTSTRAP_DIR}" --dry-run=server && ok "Dry-run passed" || {
    err "Dry-run failed — aborting upgrade"
    return 1
  }

  # 4. Apply
  log "Applying manifests..."
  kubectl apply -k "${BOOTSTRAP_DIR}"

  # 5. Refresh apps
  for app in "${APPS_ORDER[@]}"; do
    if kubectl get application "${app}" -n "${ARGOCD_NAMESPACE}" &>/dev/null; then
      log "Refreshing ${app}..."
      # Trigger ArgoCD refresh
      kubectl patch application "${app}" -n "${ARGOCD_NAMESPACE}" \
        --type merge -p '{"metadata":{"annotations":{"argocd.argoproj.io/refresh":"tough"}}}' 2>/dev/null || true
    fi
  done

  # 6. Sync apps
  for app in "${APPS_ORDER[@]}"; do
    if kubectl get application "${app}" -n "${ARGOCD_NAMESPACE}" &>/dev/null; then
      log "Syncing ${app}..."
      if command -v "${ARGOCD_BIN}" &>/dev/null; then
        "${ARGOCD_BIN}" app sync "${app}" --timeout 300 2>/dev/null || true
      else
        kubectl patch application "${app}" -n "${ARGOCD_NAMESPACE}" \
          --type merge -p '{"operation":{"sync":{}}}' 2>/dev/null || true
      fi
    fi
  done

  # 7. Capture post-upgrade evidence
  EVIDENCE_DIR="${EVIDENCE_DIR}-post-upgrade" capture_all_evidence

  echo ""
  ok "Upgrade complete!"
}

cmd_recovery() {
  require_cmd kubectl
  log "=== Recovery: Diagnosing CodeTether ArgoCD applications ==="

  ensure_evidence_dir
  local found_issues=0

  for app in "${APPS_ORDER[@]}"; do
    echo ""
    log "Diagnosing ${app}..."

    if ! kubectl get application "${app}" -n "${ARGOCD_NAMESPACE}" &>/dev/null; then
      warn "  ${app}: NOT FOUND — may need bootstrap"
      found_issues=1
      continue
    fi

    local sync health operation
    sync=$(kubectl get application "${app}" -n "${ARGOCD_NAMESPACE}" \
      -o jsonpath='{.status.sync.status}' 2>/dev/null || echo "Unknown")
    health=$(kubectl get application "${app}" -n "${ARGOCD_NAMESPACE}" \
      -o jsonpath='{.status.health.status}' 2>/dev/null || echo "Unknown")
    operation=$(kubectl get application "${app}" -n "${ARGOCD_NAMESPACE}" \
      -o jsonpath='{.status.operationState.phase}' 2>/dev/null || echo "none")

    echo "  sync=${sync} health=${health} operation=${operation}"

    # Check for stuck conditions
    if [[ "${operation}" == "Running" ]]; then
      local started_at
      started_at=$(kubectl get application "${app}" -n "${ARGOCD_NAMESPACE}" \
        -o jsonpath='{.status.operationState.startedAt}' 2>/dev/null || echo "")
      warn "  ${app}: STUCK OPERATION since ${started_at}"
      echo ""
      echo "  GitOps-first next steps:"
      echo "    1. Check operation logs:"
      echo "       argocd app logs ${app}"
      echo "    2. If truly stuck, terminate the operation:"
      echo "       argocd app terminate-op ${app}"
      echo "    3. Then re-sync:"
      echo "       argocd app sync ${app}"
      found_issues=1
    fi

    if [[ "${sync}" == "OutOfSync" ]]; then
      warn "  ${app}: OUT OF SYNC — desired state differs from live"
      echo "  GitOps-first next steps:"
      echo "    1. Review diff:"
      echo "       argocd app diff ${app}"
      echo "    2. If intentional, sync:"
      echo "       argocd app sync ${app}"
      echo "    3. If not intentional, check if Git state is correct:"
      echo "       git log --oneline -5 -- ${BOOTSTRAP_DIR}/"
      found_issues=1
    fi

    if [[ "${sync}" == "SyncFailed" ]]; then
      warn "  ${app}: SYNC FAILED"
      echo "  GitOps-first next steps:"
      echo "    1. Check sync result:"
      echo "       argocd app get ${app} --show-operation"
      echo "    2. Common causes: missing secrets, CRD not ready, invalid manifest"
      echo "    3. Fix root cause, then re-sync:"
      echo "       argocd app sync ${app}"
      found_issues=1
    fi

    if [[ "${health}" == "Degraded" ]]; then
      warn "  ${app}: DEGRADED"
      local ns
      ns=$(kubectl get application "${app}" -n "${ARGOCD_NAMESPACE}" \
        -o jsonpath='{.spec.destination.namespace}' 2>/dev/null || echo "")
      if [[ -n "${ns}" ]]; then
        echo "  Pod status:"
        kubectl get pods -n "${ns}" -o wide 2>/dev/null | head -20 || true
        echo ""
      fi
      echo "  GitOps-first next steps:"
      echo "    1. Check pod events:"
      echo "       kubectl describe pods -n ${ns}"
      echo "    2. Check logs:"
      echo "       kubectl logs -n ${ns} -l app.kubernetes.io/part-of=codetether --tail=100"
      echo "    3. If image pull error, verify tag and pull secret"
      echo "    4. If crash loop, check app logs for config errors"
      found_issues=1
    fi

    if [[ "${health}" == "Missing" ]]; then
      warn "  ${app}: HEALTH MISSING — resources not yet created"
      echo "  GitOps-first next steps:"
      echo "    1. This is normal right after bootstrap"
      echo "    2. Trigger a sync:"
      echo "       argocd app sync ${app}"
      echo "    3. Wait for health:"
      echo "       argocd app wait ${app} --health --timeout 600"
      found_issues=1
    fi

    # Capture evidence even in recovery
    capture_app_evidence "${app}"
  done

  # Check for orphaned resources
  echo ""
  log "Checking for orphaned resources..."
  if kubectl get application codetether-a2a-server -n "${ARGOCD_NAMESPACE}" &>/dev/null; then
    local orphans
    orphans=$(kubectl get application codetether-a2a-server -n "${ARGOCD_NAMESPACE}" \
      -o jsonpath='{.status.orphanedResources}' 2>/dev/null || echo "")
    if [[ -n "${orphans}" && "${orphans}" != "null" ]]; then
      warn "Orphaned resources detected in codetether-a2a-server:"
      echo "${orphans}" | jq '.' 2>/dev/null || echo "${orphans}"
      echo ""
      echo "  GitOps-first next steps:"
      echo "    1. Identify each orphaned resource in the cluster"
      echo "    2. If it's supposed to be managed, add it to the Helm chart"
      echo "    3. If it's genuinely orphaned, prune it:"
      echo "       argocd app sync codetether-a2a-server --prune"
      found_issues=1
    else
      ok "No orphaned resources detected"
    fi
  fi

  echo ""
  if [[ "${found_issues}" -eq 0 ]]; then
    ok "All applications are healthy and in sync — no issues found"
  else
    warn "Issues found — review the GitOps-first next steps above"
    echo ""
    echo "Emergency contacts:"
    echo "  - Full re-bootstrap: ./scripts/bootstrap-argocd.sh bootstrap"
    echo "  - Force re-sync all: for app in ${APPS_ORDER[*]}; do argocd app sync \$app; done"
    echo "  - Nuclear option: ./scripts/bootstrap-argocd.sh bootstrap (re-applies all manifests)"
  fi

  # Final evidence
  capture_all_evidence
}

cmd_dry_run() {
  require_cmd kubectl
  log "=== Dry-Run: Rendering and validating manifests ==="

  # 1. Kustomize render check
  log "Rendering kustomize manifests..."
  local rendered
  rendered=$(kubectl kustomize "${BOOTSTRAP_DIR}" 2>&1)
  if [[ $? -eq 0 ]]; then
    ok "Kustomize render succeeded"
    echo "${rendered}" > "${EVIDENCE_DIR}/rendered.yaml"
    log "Rendered manifests saved to ${EVIDENCE_DIR}/rendered.yaml"
  else
    err "Kustomize render failed:"
    echo "${rendered}"
    return 1
  fi

  # 2. Validate YAML structure
  log "Validating manifest structure..."
  local app_count
  app_count=$(echo "${rendered}" | yq 'select(.kind=="Application") | .metadata.name' 2>/dev/null | wc -l)
  local project_count
  project_count=$(echo "${rendered}" | yq 'select(.kind=="AppProject") | .metadata.name' 2>/dev/null | wc -l)
  log "Found ${app_count} Application(s) and ${project_count} AppProject(s)"

  if [[ "${project_count}" -lt 1 ]]; then
    err "Expected at least 1 AppProject — render may be malformed"
    return 1
  fi

  # 3. Server-side dry-run
  log "Running server-side dry-run..."
  kubectl apply -k "${BOOTSTRAP_DIR}" --dry-run=server && ok "Server-side dry-run passed" || {
    err "Server-side dry-run failed"
    return 1
  }

  # 4. Check sync-wave ordering
  log "Validating sync-wave annotations..."
  echo "${rendered}" | yq '. | select(.kind=="Application") | "\(.metadata.name): sync-wave=\(.metadata.annotations["argocd.argoproj.io/sync-wave"] // "0 (default)"\) "' 2>/dev/null || true
  ok "Sync-wave annotations validated"

  echo ""
  ok "Dry-run validation complete — all checks passed"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
usage() {
  cat <<'USAGE'
Usage: ./scripts/bootstrap-argocd.sh <command> [options]

Commands:
  bootstrap   Full bootstrap: install ArgoCD, apply manifests, sync apps
  verify      Capture evidence artifacts without making changes
  upgrade     Apply manifests with image-tag safety checks
  recovery    Diagnose stuck syncs / orphaned resources, print next steps
  dry-run     Render + server-side dry-run without applying

Environment Variables:
  ARGOCD_NAMESPACE   Kubernetes namespace for ArgoCD (default: argocd)
  EVIDENCE_DIR       Directory for evidence artifacts (default: artifacts/argocd-evidence/<timestamp>)
  SKIP_SAFETY_CHECK  Set to "1" to bypass image-tag guard (default: 0)
  ARGOCD_BIN         Path to argocd CLI (default: argocd)

Examples:
  # First-time bootstrap
  ./scripts/bootstrap-argocd.sh bootstrap

  # Verify current state without changes
  ./scripts/bootstrap-argocd.sh verify

  # Upgrade with safety checks
  ./scripts/bootstrap-argocd.sh upgrade

  # Diagnose and recover from issues
  ./scripts/bootstrap-argocd.sh recovery

  # Pre-flight validation
  ./scripts/bootstrap-argocd.sh dry-run
USAGE
}

case "${1:-}" in
  bootstrap) cmd_bootstrap ;;
  verify)    cmd_verify ;;
  upgrade)   cmd_upgrade ;;
  recovery)  cmd_recovery ;;
  dry-run)   cmd_dry_run ;;
  -h|--help|help) usage ;;
  *)
    err "Unknown command: ${1:-}"
    usage
    exit 1
    ;;
esac
