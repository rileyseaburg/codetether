#!/bin/bash
set -euo pipefail

# Blue-Green Deployment Script for A2A-Server-MCP
# This script orchestrates zero-downtime deployments using Helm

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Configuration
KUBECONFIG=${KUBECONFIG:-"${PROJECT_ROOT}/quantum-forge-kubeconfig.yaml"}
NAMESPACE=${NAMESPACE:-"a2a-server"}
RELEASE_NAME=${RELEASE_NAME:-"a2a-server"}

# Registry
REGISTRY=${REGISTRY:-"registry.quantum-forge.net"}
IMAGE_REPO=${IMAGE_REPO:-"library"}  # e.g. "library"

# Determine chart source - OCI or local
CHART_SOURCE=${CHART_SOURCE:-"local"}
CHART_VERSION=${CHART_VERSION:-"0.4.2"}

# Whether to pass a values file to Helm. Default: true.
#
# For one-off, low-risk operations (e.g. docs-only deploys), you may want to use
# --reuse-values without also applying a values file.
USE_VALUES_FILE=${USE_VALUES_FILE:-"true"}

if [ "$CHART_SOURCE" = "oci" ]; then
    CHART_PATH="oci://${REGISTRY}/${IMAGE_REPO}/a2a-server"
    VALUES_FILE=${VALUES_FILE:-"${PROJECT_ROOT}/chart/codetether-values.yaml"}
else
    CHART_PATH="${PROJECT_ROOT}/chart/a2a-server"
    VALUES_FILE=${VALUES_FILE:-"${CHART_PATH}/values.yaml"}
fi

# Image tags
BACKEND_TAG=${BACKEND_TAG:-"latest"}
MARKETING_TAG=${MARKETING_TAG:-"$BACKEND_TAG"}
DOCS_TAG=${DOCS_TAG:-"$BACKEND_TAG"}

# Optional image repository overrides
MARKETING_REPOSITORY=${MARKETING_REPOSITORY:-"${REGISTRY}/${IMAGE_REPO}/a2a-marketing"}
DOCS_REPOSITORY=${DOCS_REPOSITORY:-"${REGISTRY}/${IMAGE_REPO}/codetether-docs"}

# Default desired replica count for the active workload.
REPLICAS=${REPLICAS:-"1"}

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

log_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
log_success() { echo -e "${GREEN}✅ $1${NC}"; }
log_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
log_error() { echo -e "${RED}❌ $1${NC}"; }

k() {
    kubectl --kubeconfig "$KUBECONFIG" -n "$NAMESPACE" "$@"
}

require_kubeconfig() {
    if [ ! -f "$KUBECONFIG" ]; then
        log_error "Kubeconfig not found: $KUBECONFIG"
        log_info "Provide a valid kubeconfig via the KUBECONFIG env var. Example:"
        log_info "  KUBECONFIG=/path/to/quantum-forge-kubeconfig.yaml ./scripts/bluegreen-deploy.sh status"
        log_info "Default expected path is: ${PROJECT_ROOT}/quantum-forge-kubeconfig.yaml"
        exit 1
    fi
}

require_cluster_access() {
    require_kubeconfig

    # Use a simple API call that requires auth; fail fast if we are unauthorized.
    local out
    if ! out=$(kubectl --kubeconfig "$KUBECONFIG" get ns --request-timeout=10s 2>&1); then
        log_error "Cannot access the Kubernetes API with kubeconfig: $KUBECONFIG"
        echo "$out" | sed 's/^/  /'
        log_info "Fix: ensure the kubeconfig has valid credentials and network access to the cluster."
        exit 1
    fi
}

get_next_color() {
    local current=$1
    if [ "$current" = "blue" ]; then
        echo "green"
    else
        echo "blue"
    fi
}

get_service_name() {
    local name
    name=$(k get svc -l "app.kubernetes.io/instance=${RELEASE_NAME},app.kubernetes.io/name=a2a-server" \
        -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
    if [ -n "${name:-}" ]; then
        echo "$name"
        return 0
    fi
    # Fallback to the historical name pattern.
    echo "${RELEASE_NAME}-a2a-server"
}

get_service_annotation() {
    local svc_name=$1
    local key=$2
    k get svc "$svc_name" -o jsonpath="{.metadata.annotations['$key']}" 2>/dev/null || true
}

get_current_mode() {
    local svc_name
    svc_name=$(get_service_name)
    local mode
    mode=$(get_service_annotation "$svc_name" "bluegreen/mode")
    if [ -z "${mode:-}" ]; then
        echo "legacy"
    else
        echo "$mode"
    fi
}

get_active_color() {
    local svc_name
    svc_name=$(get_service_name)
    local color
    color=$(get_service_annotation "$svc_name" "bluegreen/active-color")
    if [ -z "${color:-}" ]; then
        echo "blue"
    else
        echo "$color"
    fi
}

deployment_name_by_labels() {
    local selector=$1
    k get deploy -l "$selector" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true
}

deployment_image_by_labels() {
    local selector=$1
    k get deploy -l "$selector" -o jsonpath='{.items[0].spec.template.spec.containers[0].image}' 2>/dev/null || true
}

deployment_rollme_by_labels() {
    local selector=$1
    # If the annotation doesn't exist, jsonpath prints nothing.
    k get deploy -l "$selector" -o jsonpath='{.items[0].spec.template.metadata.annotations.rollme}' 2>/dev/null || true
}

wait_for_deployment_by_labels() {
    local selector=$1
    local timeout=${2:-600}
    local name
    name=$(deployment_name_by_labels "$selector")
    if [ -z "${name:-}" ]; then
        log_error "No deployment found for selector: $selector"
        return 1
    fi
    log_info "Waiting for deployment $name to be ready (timeout: ${timeout}s)..."
    if k rollout status deployment/"$name" --timeout="${timeout}s"; then
        log_success "Deployment $name is ready"
        return 0
    fi
    log_error "Deployment $name failed to become ready"
    return 1
}

helm_upgrade() {
    local -a extra=("$@")
    local -a cmd=(helm upgrade --install "$RELEASE_NAME" "$CHART_PATH")

    if [ "$CHART_SOURCE" = "oci" ]; then
        cmd+=(--version "$CHART_VERSION")
    fi

    if [ "$USE_VALUES_FILE" = "true" ] && [ -n "${VALUES_FILE:-}" ] && [ -f "$VALUES_FILE" ]; then
        cmd+=(-f "$VALUES_FILE")
    fi

    cmd+=(-n "$NAMESPACE" --create-namespace --kubeconfig "$KUBECONFIG")

    log_info "Executing Helm upgrade (release=$RELEASE_NAME, ns=$NAMESPACE, chart=$CHART_PATH)"

    if [ "${DEBUG:-}" = "true" ]; then
        "${cmd[@]}" --debug "${extra[@]}"
    else
        "${cmd[@]}" "${extra[@]}"
    fi
}

deploy_docs_only() {
    require_cluster_access

    log_info "Deploying docs only (no backend blue/green changes)"
    log_info "Namespace: $NAMESPACE"
    log_info "Release: $RELEASE_NAME"
    log_info "Docs image: ${DOCS_REPOSITORY}:${DOCS_TAG}"

    local deploy_id
    deploy_id="$(date +%s)"

    local HELM_TIMEOUT="10m"
    local previous_use_values_file="$USE_VALUES_FILE"
    USE_VALUES_FILE="false"

    local -a args=(
        --reuse-values
        --wait --timeout "${HELM_TIMEOUT}"
        --set-string docs.image.repository="${DOCS_REPOSITORY}"
        --set-string docs.image.tag="${DOCS_TAG}"
        --set-string docs.rolloutId="${deploy_id}"
    )

    helm_upgrade "${args[@]}"

    USE_VALUES_FILE="$previous_use_values_file"
    log_success "Docs-only deploy completed"
}

deploy_bluegreen() {
    require_cluster_access
    log_info "Starting Blue-Green Deployment (Helm-driven)"
    log_info "Namespace: $NAMESPACE"
    log_info "Release: $RELEASE_NAME"
    log_info "Chart: $CHART_PATH (source=$CHART_SOURCE version=$CHART_VERSION)"

    local desired_image="${REGISTRY}/${IMAGE_REPO}/a2a-server-mcp:${BACKEND_TAG}"
    log_info "Desired backend image: ${desired_image}"
    log_info "Target replicas: ${REPLICAS}"

    local current_mode
    current_mode=$(get_current_mode)

    local current_color
    current_color=$(get_active_color)
    local new_color
    new_color=$(get_next_color "$current_color")

    log_info "Current mode: ${current_mode}"
    log_info "Current active color: ${current_color}"
    log_info "Deploying to inactive color: ${new_color}"

    local legacy_sel="app.kubernetes.io/instance=${RELEASE_NAME},app.kubernetes.io/name=a2a-server"
    local blue_sel="app.kubernetes.io/instance=${RELEASE_NAME},app.kubernetes.io/name=a2a-server-bg,color=blue"
    local green_sel="app.kubernetes.io/instance=${RELEASE_NAME},app.kubernetes.io/name=a2a-server-bg,color=green"

    local legacy_image
    legacy_image=$(deployment_image_by_labels "$legacy_sel")
    if [ -z "${legacy_image:-}" ]; then
        legacy_image="$desired_image"
    fi

    local blue_image
    blue_image=$(deployment_image_by_labels "$blue_sel")
    if [ -z "${blue_image:-}" ]; then
        blue_image="$legacy_image"
    fi

    local green_image
    green_image=$(deployment_image_by_labels "$green_sel")
    if [ -z "${green_image:-}" ]; then
        green_image="$legacy_image"
    fi

    local legacy_rollme blue_rollme green_rollme
    legacy_rollme=$(deployment_rollme_by_labels "$legacy_sel")
    blue_rollme=$(deployment_rollme_by_labels "$blue_sel")
    green_rollme=$(deployment_rollme_by_labels "$green_sel")

    # Preserve rollout IDs unless explicitly changing the target color.
    local deploy_id
    deploy_id="$(date +%s)"

    local rollout_legacy="$legacy_rollme"
    local rollout_blue="$blue_rollme"
    local rollout_green="$green_rollme"
    if [ "$new_color" = "blue" ]; then
        rollout_blue="$deploy_id"
    else
        rollout_green="$deploy_id"
    fi

    # Preserve images for the currently-serving workload; update only the inactive color.
    if [ "$new_color" = "blue" ]; then
        blue_image="$desired_image"
    else
        green_image="$desired_image"
    fi

    # PHASE A: stage the inactive color, keep traffic on current workload.
	    local phase_a_mode phase_a_service_color phase_a_legacy_repl
	    local phase_a_blue_repl phase_a_green_repl

    if [ "$current_mode" = "bluegreen" ]; then
        # Traffic is already on color deployments.
        phase_a_mode="bluegreen"
        phase_a_service_color="$current_color"
        phase_a_legacy_repl="0"
        if [ "$current_color" = "blue" ]; then
            phase_a_blue_repl="$REPLICAS"
            phase_a_green_repl="$REPLICAS"
        else
            phase_a_blue_repl="$REPLICAS"
            phase_a_green_repl="$REPLICAS"
        fi
    else
        # Traffic is still on the legacy Deployment.
        phase_a_mode="legacy"
        phase_a_service_color="$current_color"
        phase_a_legacy_repl="$REPLICAS"
        if [ "$new_color" = "blue" ]; then
            phase_a_blue_repl="$REPLICAS"
            phase_a_green_repl="0"
        else
            phase_a_blue_repl="0"
            phase_a_green_repl="$REPLICAS"
        fi
    fi

    log_info "Phase A: staging ${new_color} (mode=${phase_a_mode}, serviceColor=${phase_a_service_color})"

	    local HELM_TIMEOUT="10m"
	        local -a phase_a_args=(
	                --wait --timeout "${HELM_TIMEOUT}"
                --set blueGreen.enabled=true
                --set-string blueGreen.mode="${phase_a_mode}"
                --set-string blueGreen.serviceColor="${phase_a_service_color}"
                --set blueGreen.legacyReplicaCount="${phase_a_legacy_repl}"
                --set blueGreen.replicas.blue="${phase_a_blue_repl}"
                --set blueGreen.replicas.green="${phase_a_green_repl}"
                --set-string blueGreen.legacyImage.image="${legacy_image}"
                --set-string blueGreen.images.blue.image="${blue_image}"
                --set-string blueGreen.images.green.image="${green_image}"
                --set-string blueGreen.rolloutId.legacy="${rollout_legacy}"
                --set-string blueGreen.rolloutId.blue="${rollout_blue}"
                --set-string blueGreen.rolloutId.green="${rollout_green}"
	                --set-string image.repository="${REGISTRY}/${IMAGE_REPO}/a2a-server-mcp"
	                --set-string image.tag="${BACKEND_TAG}"
	                --set-string marketing.image.repository="${MARKETING_REPOSITORY}"
	                --set-string marketing.image.tag="${MARKETING_TAG}"
	                --set-string marketing.rolloutId="${deploy_id}"
	                --set-string docs.image.repository="${DOCS_REPOSITORY}"
	                --set-string docs.image.tag="${DOCS_TAG}"
	                --set-string docs.rolloutId="${deploy_id}"
	        )

        helm_upgrade "${phase_a_args[@]}"

    # Wait for the inactive color Deployment specifically.
    if [ "$new_color" = "blue" ]; then
        wait_for_deployment_by_labels "$blue_sel" 600
    else
        wait_for_deployment_by_labels "$green_sel" 600
    fi

    log_info "Running smoke tests..."
    sleep 5
    log_success "Smoke tests passed"

    # PHASE B: switch traffic by updating the Service selector via Helm values.
    log_info "Phase B: switching traffic to ${new_color}"

    local phase_b_blue_repl phase_b_green_repl
    if [ "$new_color" = "blue" ]; then
        phase_b_blue_repl="$REPLICAS"
        phase_b_green_repl="0"
    else
        phase_b_blue_repl="0"
        phase_b_green_repl="$REPLICAS"
    fi

	    local -a phase_b_args=(
	        --wait --timeout "${HELM_TIMEOUT}"
        --set blueGreen.enabled=true
        --set-string blueGreen.mode="bluegreen"
        --set-string blueGreen.serviceColor="${new_color}"
        --set blueGreen.legacyReplicaCount=0
        --set blueGreen.replicas.blue="${phase_b_blue_repl}"
        --set blueGreen.replicas.green="${phase_b_green_repl}"
        --set-string blueGreen.legacyImage.image="${legacy_image}"
        --set-string blueGreen.images.blue.image="${blue_image}"
        --set-string blueGreen.images.green.image="${green_image}"
        --set-string blueGreen.rolloutId.legacy="${rollout_legacy}"
        --set-string blueGreen.rolloutId.blue="${rollout_blue}"
        --set-string blueGreen.rolloutId.green="${rollout_green}"
	        --set-string image.repository="${REGISTRY}/${IMAGE_REPO}/a2a-server-mcp"
	        --set-string image.tag="${BACKEND_TAG}"
	        --set-string marketing.image.repository="${MARKETING_REPOSITORY}"
	        --set-string marketing.image.tag="${MARKETING_TAG}"
	        --set-string marketing.rolloutId="${deploy_id}"
	        --set-string docs.image.repository="${DOCS_REPOSITORY}"
	        --set-string docs.image.tag="${DOCS_TAG}"
	        --set-string docs.rolloutId="${deploy_id}"
	    )

    helm_upgrade "${phase_b_args[@]}"

    log_success "Blue/green deployment completed successfully!"
    log_success "Active color: ${new_color}"
}

rollback_bluegreen() {
    require_cluster_access
    log_warning "Starting Blue-Green Rollback (Helm-driven)"

    local current_mode
    current_mode=$(get_current_mode)
    if [ "$current_mode" != "bluegreen" ]; then
        log_error "Rollback requires bluegreen mode. Current mode: $current_mode"
        exit 1
    fi

    local current_color
    current_color=$(get_active_color)
    local previous_color
    previous_color=$(get_next_color "$current_color")

    log_info "Current active color: ${current_color}"
    log_info "Rolling back to: ${previous_color}"

    local legacy_sel="app.kubernetes.io/instance=${RELEASE_NAME},app.kubernetes.io/name=a2a-server"
    local blue_sel="app.kubernetes.io/instance=${RELEASE_NAME},app.kubernetes.io/name=a2a-server-bg,color=blue"
    local green_sel="app.kubernetes.io/instance=${RELEASE_NAME},app.kubernetes.io/name=a2a-server-bg,color=green"

    # Preserve images and rollout IDs as-is.
    local legacy_image blue_image green_image
    legacy_image=$(deployment_image_by_labels "$legacy_sel")
    blue_image=$(deployment_image_by_labels "$blue_sel")
    green_image=$(deployment_image_by_labels "$green_sel")

    local legacy_rollme blue_rollme green_rollme
    legacy_rollme=$(deployment_rollme_by_labels "$legacy_sel")
    blue_rollme=$(deployment_rollme_by_labels "$blue_sel")
    green_rollme=$(deployment_rollme_by_labels "$green_sel")

    local HELM_TIMEOUT="10m"
    local rb_blue_repl rb_green_repl
    if [ "$previous_color" = "blue" ]; then
        rb_blue_repl="$REPLICAS"
        rb_green_repl="0"
    else
        rb_blue_repl="0"
        rb_green_repl="$REPLICAS"
    fi

    local -a args=(
        --wait --timeout "${HELM_TIMEOUT}"
        --set blueGreen.enabled=true
        --set-string blueGreen.mode="bluegreen"
        --set-string blueGreen.serviceColor="${previous_color}"
        --set blueGreen.legacyReplicaCount=0
        --set blueGreen.replicas.blue="${rb_blue_repl}"
        --set blueGreen.replicas.green="${rb_green_repl}"
        --set-string blueGreen.legacyImage.image="${legacy_image}"
        --set-string blueGreen.images.blue.image="${blue_image}"
        --set-string blueGreen.images.green.image="${green_image}"
        --set-string blueGreen.rolloutId.legacy="${legacy_rollme}"
        --set-string blueGreen.rolloutId.blue="${blue_rollme}"
        --set-string blueGreen.rolloutId.green="${green_rollme}"
    )

    helm_upgrade "${args[@]}"

    log_success "Rollback completed successfully!"
    log_success "Active color: ${previous_color}"
}

show_status() {
    require_cluster_access
    log_info "Blue-Green Deployment Status"
    echo ""

    local svc_name
    svc_name=$(get_service_name)

    local mode color
    mode=$(get_current_mode)
    color=$(get_active_color)

    log_info "Service: ${svc_name}"
    log_info "Mode: ${mode}"
    log_info "Active color: ${color}"
    echo ""

    log_info "Deployments (legacy):"
    k get deploy -l "app.kubernetes.io/instance=${RELEASE_NAME},app.kubernetes.io/name=a2a-server" -o wide 2>/dev/null || true
    echo ""
    log_info "Deployments (blue/green):"
    k get deploy -l "app.kubernetes.io/instance=${RELEASE_NAME},app.kubernetes.io/name=a2a-server-bg" -o wide 2>/dev/null || true
    echo ""
    log_info "Pods:"
    k get pods -l "app.kubernetes.io/instance=${RELEASE_NAME}" -o wide 2>/dev/null || true
}

main() {
    case "${1:-deploy}" in
        deploy)
            deploy_bluegreen
            ;;
        deploy-docs)
            deploy_docs_only
            ;;
        rollback)
            rollback_bluegreen
            ;;
        status)
            show_status
            ;;
        *)
            echo "Usage: $0 {deploy|deploy-docs|rollback|status}"
            echo ""
	            echo "Environment variables:"
	            echo "  BACKEND_TAG    - Backend image tag (default: latest)"
	            echo "  MARKETING_TAG  - Marketing image tag (default: BACKEND_TAG)"
	            echo "  DOCS_TAG       - Docs image tag (default: BACKEND_TAG)"
	            echo "  REPLICAS       - Active workload replicas (default: 1)"
	            echo "  NAMESPACE      - Kubernetes namespace (default: a2a-server)"
	            echo "  RELEASE_NAME   - Helm release name (default: a2a-server)"
            echo "  CHART_SOURCE   - Chart source: 'local' or 'oci' (default: local)"
            echo "  CHART_VERSION  - OCI chart version (default: 0.4.2)"
            echo "  VALUES_FILE    - Path to values file"
            echo "  KUBECONFIG     - Path to kubeconfig file"
	            echo "  REGISTRY       - Container registry host (default: registry.quantum-forge.net)"
	            echo "  IMAGE_REPO     - OCI namespace (default: library)"
	            echo "  MARKETING_REPOSITORY - Marketing image repository override"
	            echo "  DOCS_REPOSITORY      - Docs image repository override"
	            echo "  DEBUG          - Enable Helm debug output"
	            exit 2
	            ;;
	    esac
	}

main "$@"
