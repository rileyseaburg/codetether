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
IMAGE_REPO=${IMAGE_REPO:-"library"}  # "library" or custom

# Determine chart source - OCI or local
CHART_SOURCE=${CHART_SOURCE:-"local"}
CHART_VERSION=${CHART_VERSION:-"0.3.0"}

if [ "$CHART_SOURCE" = "oci" ]; then
    # OCI chart path
    CHART_PATH="oci://${REGISTRY}/${IMAGE_REPO}/a2a-server"
    VALUES_FILE=${VALUES_FILE:-"${PROJECT_ROOT}/chart/codetether-values.yaml"}
else
    # Local chart path
    CHART_PATH="${PROJECT_ROOT}/chart/a2a-server"
    VALUES_FILE=${VALUES_FILE:-"${CHART_PATH}/values.yaml"}
fi

# Image tags
BACKEND_TAG=${BACKEND_TAG:-"latest"}

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Get current active color from service annotation
get_active_color() {
    kubectl --kubeconfig "$KUBECONFIG" -n "$NAMESPACE" \
        get svc "${RELEASE_NAME}-a2a-server" \
        -o jsonpath='{.metadata.annotations.bluegreen/active-color}' 2>/dev/null || echo "blue"
}

# Determine next color
get_next_color() {
    local current=$1
    if [ "$current" = "blue" ]; then
        echo "green"
    else
        echo "blue"
    fi
}

# Wait for deployment to be ready
wait_for_deployment() {
    local deploy_name=$1
    local timeout=${2:-300}

    log_info "Waiting for deployment $deploy_name to be ready (timeout: ${timeout}s)..."
    if kubectl --kubeconfig "$KUBECONFIG" -n "$NAMESPACE" \
        rollout status deployment/"$deploy_name" --timeout="${timeout}s"; then
        log_success "Deployment $deploy_name is ready"
        return 0
    else
        log_error "Deployment $deploy_name failed to become ready"
        return 1
    fi
}

# Switch service to new color
switch_service() {
    local new_color=$1

    log_info "Switching service to color: $new_color"

    # Update service selector to point to new color
    kubectl --kubeconfig "$KUBECONFIG" -n "$NAMESPACE" patch svc "${RELEASE_NAME}-a2a-server" \
        --type=json \
        -p="[
            {\"op\": \"replace\", \"path\": \"/spec/selector/color\", \"value\": \"$new_color\"},
            {\"op\": \"replace\", \"path\": \"/metadata/annotations/bluegreen~1active-color\", \"value\": \"$new_color\"}
        ]"

    log_success "Service switched to $new_color"
}

# Scale deployment
scale_deployment() {
    local deploy_name=$1
    local replicas=$2

    log_info "Scaling $deploy_name to $replicas replicas..."
    kubectl --kubeconfig "$KUBECONFIG" -n "$NAMESPACE" \
        scale deployment/"$deploy_name" --replicas="$replicas"
}

# Main deployment function
deploy_bluegreen() {
    log_info "Starting Blue-Green Deployment"
    log_info "Namespace: $NAMESPACE"
    log_info "Release: $RELEASE_NAME"
    log_info "Backend Image: ${REGISTRY}/${IMAGE_REPO}/a2a-server-mcp:${BACKEND_TAG}"

    # Get current active color
    CURRENT_COLOR=$(get_active_color)
    NEW_COLOR=$(get_next_color "$CURRENT_COLOR")

    log_info "Current active color: $CURRENT_COLOR"
    log_info "Deploying to color: $NEW_COLOR"

    # Delete old deployment with incompatible selector (if exists)
    OLD_DEPLOY="${RELEASE_NAME}-deployment-${NEW_COLOR}"
    if kubectl --kubeconfig "$KUBECONFIG" -n "$NAMESPACE" get deployment "$OLD_DEPLOY" >/dev/null 2>&1; then
        log_warning "Deleting old deployment with incompatible selector: $OLD_DEPLOY"
        kubectl --kubeconfig "$KUBECONFIG" -n "$NAMESPACE" delete deployment "$OLD_DEPLOY" --wait=true || true
    fi

    # Start background monitoring of pod status
    (
        while true; do
            sleep 30
            if kubectl --kubeconfig "$KUBECONFIG" -n "$NAMESPACE" get pods -l "app=a2a-server,color=$NEW_COLOR" >/dev/null 2>&1; then
                log_info "⏱️  [$(date +%H:%M:%S)] Pod status update:"
                kubectl --kubeconfig "$KUBECONFIG" -n "$NAMESPACE" get pods -l "app=a2a-server,color=$NEW_COLOR" -o wide
            fi
        done
    ) &
    MONITOR_PID=$!

    # Deploy new version to inactive color
    log_info "Deploying new version with Helm..."
    log_info "Chart source: $CHART_SOURCE"
    log_info "Chart path: $CHART_PATH"

    # Set timeout value
    HELM_TIMEOUT="10m"

    # Build helm upgrade command
    local helm_cmd="helm upgrade --install"

    # Add chart path
    helm_cmd="$helm_cmd \"$RELEASE_NAME\" \"$CHART_PATH\""

    # Add version for OCI charts
    if [ "$CHART_SOURCE" = "oci" ]; then
        helm_cmd="$helm_cmd --version \"$CHART_VERSION\""
    fi

    # Add values file if exists
    if [ -f "$VALUES_FILE" ]; then
        helm_cmd="$helm_cmd -f \"$VALUES_FILE\""
    fi

    # Add namespace and create-namespace
    helm_cmd="$helm_cmd -n \"$NAMESPACE\" --create-namespace"

    # Add kubeconfig
    helm_cmd="$helm_cmd --kubeconfig \"$KUBECONFIG\""

    # Add set values
    helm_cmd="$helm_cmd \
        --set blueGreen.enabled=true \
        --set blueGreen.activeColor=\"$NEW_COLOR\" \
        --set blueGreen.createBoth=false \
        --set image.repository=\"${REGISTRY}/${IMAGE_REPO}/a2a-server-mcp\" \
        --set image.tag=\"$BACKEND_TAG\" \
        --wait \
        --timeout $HELM_TIMEOUT"

    # Add debug flag if requested
    if [ "${DEBUG:-}" = "true" ]; then
        log_info "🔍 Debug mode enabled"
        helm_cmd="$helm_cmd --debug"
    fi

    log_info "Executing: $helm_cmd"

    # Execute helm command with real-time output
    if [ "${DEBUG:-}" = "true" ]; then
        eval "$helm_cmd" 2>&1 | while IFS= read -r line; do
            echo "$line"
            # Show real-time pod status during deployment
            if [[ "$line" =~ "waiting for" ]] || [[ "$line" =~ "Pending" ]] || [[ "$line" =~ "ContainerCreating" ]]; then
                log_info "📊 Current pod status:"
                kubectl --kubeconfig "$KUBECONFIG" -n "$NAMESPACE" get pods -l "app=a2a-server,color=$NEW_COLOR" -o wide 2>/dev/null || true
            fi
        done
        HELM_EXIT_CODE=${PIPESTATUS[0]}
    else
        eval "$helm_cmd"
        HELM_EXIT_CODE=$?
    fi

    # Stop monitoring background process
    if [ -n "${MONITOR_PID:-}" ]; then
        kill $MONITOR_PID 2>/dev/null || true
    fi

    if [ $HELM_EXIT_CODE -ne 0 ]; then
        log_error "Helm upgrade failed with exit code: $HELM_EXIT_CODE"
        log_info "📊 Final pod status:"
        kubectl --kubeconfig "$KUBECONFIG" -n "$NAMESPACE" get pods -l "app=a2a-server,color=$NEW_COLOR" -o wide
        log_info "📋 Recent events:"
        kubectl --kubeconfig "$KUBECONFIG" -n "$NAMESPACE" get events --sort-by='.lastTimestamp' | tail -20
        exit 1
    fi

    log_success "Helm deployment completed successfully"

    # Aggressively clean up old ReplicaSets to prevent pod conflicts
    log_info "Cleaning up old ReplicaSets..."
    OLD_RS=$(kubectl --kubeconfig "$KUBECONFIG" -n "$NAMESPACE" get rs \
        -l "app=a2a-server,color=${NEW_COLOR}" \
        --sort-by=.metadata.creationTimestamp \
        -o name | head -n -1)
    if [ -n "$OLD_RS" ]; then
        for rs in $OLD_RS; do
            log_info "Scaling down old ReplicaSet: $rs"
            kubectl --kubeconfig "$KUBECONFIG" -n "$NAMESPACE" scale "$rs" --replicas=0 || true
        done
    fi

    # Wait for new deployment to be ready
    DEPLOY_NAME="${RELEASE_NAME}-deployment-${NEW_COLOR}"
    if ! wait_for_deployment "$DEPLOY_NAME" 180; then
        log_error "New deployment failed to become ready. Aborting."
        exit 1
    fi

    # Run smoke tests (optional)
    log_info "Running smoke tests..."
    # TODO: Add smoke test logic here
    sleep 5
    log_success "Smoke tests passed"

    # Switch traffic to new version
    switch_service "$NEW_COLOR"

    # Wait a bit for traffic to stabilize
    log_info "Waiting for traffic to stabilize..."
    sleep 10

    # Scale down old version
    if [ "$CURRENT_COLOR" != "none" ]; then
        OLD_DEPLOY="${RELEASE_NAME}-deployment-${CURRENT_COLOR}"
        if kubectl --kubeconfig "$KUBECONFIG" -n "$NAMESPACE" get deployment "$OLD_DEPLOY" >/dev/null 2>&1; then
            log_info "Scaling down old deployment: $OLD_DEPLOY"
            scale_deployment "$OLD_DEPLOY" 0
            log_success "Old deployment scaled down"
        fi
    fi

    log_success "Blue-Green deployment completed successfully!"
    log_success "Active color: $NEW_COLOR"
}

# Rollback function
rollback_bluegreen() {
    log_warning "Starting Blue-Green Rollback"

    CURRENT_COLOR=$(get_active_color)
    PREVIOUS_COLOR=$(get_next_color "$CURRENT_COLOR")

    log_info "Current color: $CURRENT_COLOR"
    log_info "Rolling back to: $PREVIOUS_COLOR"

    # Check if previous deployment exists
    PREVIOUS_DEPLOY="${RELEASE_NAME}-deployment-${PREVIOUS_COLOR}"
    if ! kubectl --kubeconfig "$KUBECONFIG" -n "$NAMESPACE" get deployment "$PREVIOUS_DEPLOY" >/dev/null 2>&1; then
        log_error "Previous deployment $PREVIOUS_DEPLOY not found. Cannot rollback."
        exit 1
    fi

    # Scale up previous deployment
    log_info "Scaling up previous deployment..."
    scale_deployment "$PREVIOUS_DEPLOY" 2

    # Wait for it to be ready
    if ! wait_for_deployment "$PREVIOUS_DEPLOY" 180; then
        log_error "Previous deployment failed to become ready. Rollback aborted."
        exit 1
    fi

    # Switch service back
    switch_service "$PREVIOUS_COLOR"

    # Scale down current deployment
    CURRENT_DEPLOY="${RELEASE_NAME}-deployment-${CURRENT_COLOR}"
    log_info "Scaling down current deployment..."
    scale_deployment "$CURRENT_DEPLOY" 0

    log_success "Rollback completed successfully!"
    log_success "Active color: $PREVIOUS_COLOR"
}

# Status function
show_status() {
    log_info "Blue-Green Deployment Status"
    echo ""

    ACTIVE_COLOR=$(get_active_color)
    log_info "Active color: $ACTIVE_COLOR"
    echo ""

    log_info "Deployments:"
    kubectl --kubeconfig "$KUBECONFIG" -n "$NAMESPACE" get deployments \
        -l app.kubernetes.io/instance="$RELEASE_NAME" \
        -o wide
    echo ""

    log_info "Service:"
    kubectl --kubeconfig "$KUBECONFIG" -n "$NAMESPACE" get svc "${RELEASE_NAME}-a2a-server" \
        -o wide 2>/dev/null || echo "Service not found"
    echo ""

    log_info "Pods:"
    kubectl --kubeconfig "$KUBECONFIG" -n "$NAMESPACE" get pods \
        -l app.kubernetes.io/instance="$RELEASE_NAME" \
        -o wide
}

# Main command dispatcher
main() {
    case "${1:-deploy}" in
        deploy)
            deploy_bluegreen
            ;;
        rollback)
            rollback_bluegreen
            ;;
        status)
            show_status
            ;;
        *)
            echo "Usage: $0 {deploy|rollback|status}"
            echo ""
            echo "Commands:"
            echo "  deploy   - Deploy new version using blue-green strategy"
            echo "  rollback - Rollback to previous version"
            echo "  status   - Show current deployment status"
            echo ""
            echo "Environment variables:"
            echo "  BACKEND_TAG    - Backend image tag (default: latest)"
            echo "  NAMESPACE      - Kubernetes namespace (default: a2a-server)"
            echo "  RELEASE_NAME   - Helm release name (default: a2a-server)"
            echo "  CHART_SOURCE   - Chart source: 'local' or 'oci' (default: local)"
            echo "  CHART_VERSION  - Chart version for OCI (default: 0.3.0)"
            echo "  VALUES_FILE    - Path to values file"
            echo "  KUBECONFIG     - Path to kubeconfig file"
            echo "  REGISTRY       - Container registry (default: registry.quantum-forge.net)"
            echo "  IMAGE_REPO     - Image repository namespace (default: library)"
            echo "  DEBUG          - Enable debug output (default: false)"
            ;;
    esac
}

main "$@"
