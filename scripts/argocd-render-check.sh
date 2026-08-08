#!/usr/bin/env bash
# =============================================================================
# Static manifest renderability check for deploy/argocd
# Runs in CI without a cluster (client-side only)
# =============================================================================
set -euo pipefail

BOOTSTRAP_DIR="${1:-deploy/argocd}"
errors=0

echo "=== ArgoCD Manifest Renderability Check ==="

# 1. Kustomize render
echo -n "Kustomize render... "
rendered=$(kubectl kustomize "${BOOTSTRAP_DIR}" 2>&1) || {
  echo "FAIL"
  echo "  Error: ${rendered}"
  errors=$((errors + 1))
  rendered=""
}
if [[ -n "${rendered}" ]]; then
  echo "OK"
fi

if [[ -z "${rendered}" ]]; then
  echo "Cannot continue — kustomize render failed"
  exit 1
fi

# 2. Check required kinds
echo -n "Checking for AppProject... "
project_count=$(echo "${rendered}" | yq 'select(.kind=="AppProject") | .metadata.name' 2>/dev/null | wc -l)
if [[ "${project_count}" -ge 1 ]]; then
  echo "OK (${project_count} found)"
else
  echo "FAIL — no AppProject found"
  errors=$((errors + 1))
fi

echo -n "Checking for Applications... "
app_count=$(echo "${rendered}" | yq 'select(.kind=="Application") | .metadata.name' 2>/dev/null | wc -l)
if [[ "${app_count}" -ge 1 ]]; then
  echo "OK (${app_count} found)"
else
  echo "FAIL — no Applications found"
  errors=$((errors + 1))
fi

# 3. Validate each Application has required fields
echo -n "Validating Application spec fields... "
app_errors=0
while IFS= read -r app_name; do
  [[ -z "${app_name}" ]] && continue
  # Check project
  project=$(echo "${rendered}" | yq ". | select(.kind==\"Application\" and .metadata.name==\"${app_name}\") | .spec.project // \"\"" 2>/dev/null)
  if [[ -z "${project}" ]]; then
    echo ""
    echo "  FAIL: ${app_name} missing spec.project"
    app_errors=$((app_errors + 1))
  fi
  # Check destination
  dest_server=$(echo "${rendered}" | yq ". | select(.kind==\"Application\" and .metadata.name==\"${app_name}\") | .spec.destination.server // \"\"" 2>/dev/null)
  if [[ -z "${dest_server}" ]]; then
    echo ""
    echo "  FAIL: ${app_name} missing spec.destination.server"
    app_errors=$((app_errors + 1))
  fi
  # Check source
  repo=$(echo "${rendered}" | yq ". | select(.kind==\"Application\" and .metadata.name==\"${app_name}\") | .spec.source.repoURL // \"\"" 2>/dev/null)
  if [[ -z "${repo}" ]]; then
    echo ""
    echo "  FAIL: ${app_name} missing spec.source.repoURL"
    app_errors=$((app_errors + 1))
  fi
done < <(echo "${rendered}" | yq 'select(.kind=="Application") | .metadata.name' 2>/dev/null)

if [[ "${app_errors}" -eq 0 ]]; then
  echo "OK"
else
  errors=$((errors + app_errors))
fi

# 4. Check sync-wave ordering (info only, not a failure)
echo -n "Sync-wave annotations: "
echo "${rendered}" | yq '. | select(.kind=="Application") | "\(.metadata.name): wave=\(.metadata.annotations["argocd.argoproj.io/sync-wave"] // "0")"' 2>/dev/null | tr '\n' ' '
echo ""

# 5. Validate YAML is parseable (redundant but safe)
echo -n "YAML parseability... "
echo "${rendered}" | yq '.' >/dev/null 2>&1 && echo "OK" || {
  echo "FAIL"
  errors=$((errors + 1))
}

# Summary
echo ""
if [[ "${errors}" -eq 0 ]]; then
  echo "=== All checks passed ==="
  exit 0
else
  echo "=== ${errors} check(s) failed ==="
  exit 1
fi
