#!/usr/bin/env bash
# Blue/Green deployment orchestration for A2A Server.
#
# Usage:
#   ./scripts/deploy-blue-green.sh <image-tag> [--skip-smoke] [--auto-rollback]
#
# Prerequisites:
#   - helm, kubectl in PATH
#   - kubectl context pointing at the target cluster
#   - Helm release 'codetether' installed in namespace 'a2a-server'
#
# The chart already supports blue-green via Helm values. This script automates
# the two-phase switch:
#   Phase 1 (Stage): Deploy new image to the INACTIVE color with 0 traffic.
#   Phase 2 (Cutover): Flip the Service selector to the new color.
#
# Optionally runs smoke tests between phases and auto-rolls back on failure.

set -euo pipefail

# ── Configuration ──────────────────────────────────────────────────────────────
RELEASE="codetether"
NAMESPACE="a2a-server"
CHART_PATH="./chart/a2a-server"
SMOKE_URL="https://api.codetether.run/.well-known/agent-card.json"
SMOKE_RETRIES=12
SMOKE_INTERVAL=5

# ── CLI args ───────────────────────────────────────────────────────────────────
IMAGE_TAG="${1:?Usage: $0 <image-tag> [--skip-smoke] [--auto-rollback]}"
SKIP_SMOKE=false
AUTO_ROLLBACK=false

for arg in "$@"; do
  case "$arg" in
    --skip-smoke)     SKIP_SMOKE=true ;;
    --auto-rollback)  AUTO_ROLLBACK=true ;;
  esac
done

# ── Helpers ────────────────────────────────────────────────────────────────────
info()  { echo -e "\033[1;34m[INFO]\033[0m  $*"; }
ok()    { echo -e "\033[1;32m[OK]\033[0m    $*"; }
warn()  { echo -e "\033[1;33m[WARN]\033[0m  $*"; }
fail()  { echo -e "\033[1;31m[FAIL]\033[0m  $*"; }

current_active_color() {
  kubectl get svc "${RELEASE}-a2a-server" -n "${NAMESPACE}" \
    -o jsonpath='{.metadata.annotations.bluegreen/active-color}' 2>/dev/null || echo "green"
}

opposite_color() {
  if [ "$1" = "blue" ]; then echo "green"; else echo "blue"; fi
}

wait_for_pods() {
  local color="$1"
  local deploy_name="${RELEASE}-a2a-server-deployment-${color}"
  info "Waiting for ${deploy_name} pods to be Ready..."
  if kubectl rollout status "deployment/${deploy_name}" -n "${NAMESPACE}" --timeout=180s; then
    ok "${deploy_name} is Ready"
  else
    fail "${deploy_name} failed to become Ready"
    return 1
  fi
}

smoke_test() {
  info "Running smoke tests against ${SMOKE_URL}..."
  for i in $(seq 1 "${SMOKE_RETRIES}"); do
    local http_code
    http_code=$(curl -sS -o /dev/null -w "%{http_code}" "${SMOKE_URL}" 2>/dev/null || echo "000")
    if [ "${http_code}" = "200" ]; then
      ok "Smoke test passed (HTTP ${http_code} on attempt ${i})"
      return 0
    fi
    info "  Attempt ${i}/${SMOKE_RETRIES}: HTTP ${http_code} — retrying in ${SMOKE_INTERVAL}s..."
    sleep "${SMOKE_INTERVAL}"
  done
  fail "Smoke test failed after ${SMOKE_RETRIES} attempts"
  return 1
}

# ── Determine colors ──────────────────────────────────────────────────────────
ACTIVE=$(current_active_color)
INACTIVE=$(opposite_color "${ACTIVE}")

info "Current active color: ${ACTIVE}"
info "Deploying new version to inactive color: ${INACTIVE}"
info "Image tag: ${IMAGE_TAG}"

# ── Phase 1: Stage new version on inactive color ──────────────────────────────
info "=== Phase 1: Staging ${INACTIVE} ==="

helm upgrade "${RELEASE}" "${CHART_PATH}" \
  --namespace "${NAMESPACE}" \
  --reuse-values \
  --set "blueGreen.enabled=true" \
  --set "blueGreen.mode=bluegreen" \
  --set "blueGreen.serviceColor=${ACTIVE}" \
  --set "blueGreen.replicas.${INACTIVE}=1" \
  --set "blueGreen.replicas.${ACTIVE}=1" \
  --set "blueGreen.images.${INACTIVE}.image=us-central1-docker.pkg.dev/spotlessbinco/codetether/a2a-server-mcp:${IMAGE_TAG}" \
  --set "blueGreen.rolloutId.${INACTIVE}=rollout-$(date +%s)" \
  --wait --timeout 180s

ok "Helm upgrade complete — ${INACTIVE} staged with ${IMAGE_TAG}"
wait_for_pods "${INACTIVE}"

# ── Smoke test (optional) ─────────────────────────────────────────────────────
if [ "${SKIP_SMOKE}" = "true" ]; then
  warn "Skipping smoke tests (--skip-smoke)"
else
  # Test against the inactive pods directly via a temporary port-forward or
  # rely on the readiness probe having passed (wait_for_pods).
  # For production safety, we verify the public endpoint still works.
  if ! smoke_test; then
    if [ "${AUTO_ROLLBACK}" = "true" ]; then
      warn "Auto-rollback: scaling ${INACTIVE} back to 0"
      helm upgrade "${RELEASE}" "${CHART_PATH}" \
        --namespace "${NAMESPACE}" \
        --reuse-values \
        --set "blueGreen.replicas.${INACTIVE}=0" \
        --wait --timeout 120s
      fail "Rolled back due to smoke test failure"
    fi
    exit 1
  fi
fi

# ── Phase 2: Cutover — switch service to inactive color ───────────────────────
info "=== Phase 2: Cutover → ${INACTIVE} ==="

helm upgrade "${RELEASE}" "${CHART_PATH}" \
  --namespace "${NAMESPACE}" \
  --reuse-values \
  --set "blueGreen.serviceColor=${INACTIVE}" \
  --wait --timeout 120s

ok "Service now routes to ${INACTIVE}"

# ── Post-cutover smoke test ───────────────────────────────────────────────────
if [ "${SKIP_SMOKE}" != "true" ]; then
  sleep 3  # Give ingress/controller a moment to converge
  if ! smoke_test; then
    fail "Post-cutover smoke test failed!"
    if [ "${AUTO_ROLLBACK}" = "true" ]; then
      warn "Auto-rollback: switching back to ${ACTIVE}"
      helm upgrade "${RELEASE}" "${CHART_PATH}" \
        --namespace "${NAMESPACE}" \
        --reuse-values \
        --set "blueGreen.serviceColor=${ACTIVE}" \
        --wait --timeout 120s
      fail "Rolled back to ${ACTIVE}"
    fi
    exit 1
  fi
fi

# ── Scale down old color ──────────────────────────────────────────────────────
info "Scaling down old ${ACTIVE} deployment to 0..."
helm upgrade "${RELEASE}" "${CHART_PATH}" \
  --namespace "${NAMESPACE}" \
  --reuse-values \
  --set "blueGreen.replicas.${ACTIVE}=0" \
  --wait --timeout 120s

ok "=== Deployment complete! ==="
ok "Active: ${INACTIVE} (${IMAGE_TAG})"
ok "Previous: ${ACTIVE} (scaled to 0, ready for next rollout)"
