#!/bin/bash
# Blue-Green Deployment for Marketing Site
# Usage: ./scripts/bluegreen-marketing.sh [deploy|rollback|status]

set -euo pipefail

NAMESPACE="${NAMESPACE:-a2a-server}"
IMAGE_REGISTRY="${IMAGE_REGISTRY:-us-central1-docker.pkg.dev/spotlessbinco/codetether}"
IMAGE_NAME="${IMAGE_NAME:-codetether-marketing}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
SERVICE_NAME="codetether-marketing"
BASE_DEPLOYMENT="codetether-marketing"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info() { echo -e "${CYAN}ℹ️  $1${NC}"; }
log_success() { echo -e "${GREEN}✅ $1${NC}"; }
log_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
log_error() { echo -e "${RED}❌ $1${NC}"; }

get_current_slot() {
    # Check which slot the service is currently pointing to
    local selector=$(kubectl get svc "$SERVICE_NAME" -n "$NAMESPACE" -o jsonpath='{.spec.selector.slot}' 2>/dev/null || echo "")
    if [ -z "$selector" ] || [ "$selector" == "null" ]; then
        # No slot selector - check if blue/green deployments exist
        if kubectl get deployment "${BASE_DEPLOYMENT}-blue" -n "$NAMESPACE" &>/dev/null; then
            echo "blue"
        elif kubectl get deployment "${BASE_DEPLOYMENT}-green" -n "$NAMESPACE" &>/dev/null; then
            echo "green"
        else
            echo "none"
        fi
    else
        echo "$selector"
    fi
}

get_inactive_slot() {
    local current=$(get_current_slot)
    if [ "$current" == "blue" ]; then
        echo "green"
    else
        echo "blue"
    fi
}

check_deployment_ready() {
    local deployment=$1
    local timeout=${2:-120}
    
    log_info "Waiting for deployment $deployment to be ready (timeout: ${timeout}s)..."
    
    if kubectl rollout status deployment/"$deployment" -n "$NAMESPACE" --timeout="${timeout}s"; then
        log_success "Deployment $deployment is ready"
        return 0
    else
        log_error "Deployment $deployment failed to become ready"
        return 1
    fi
}

health_check() {
    local deployment=$1
    local max_attempts=10
    local attempt=1
    
    log_info "Running health checks on $deployment..."
    
    # Get a pod from the deployment
    local pod=$(kubectl get pods -n "$NAMESPACE" -l "app.kubernetes.io/name=marketing,slot=$deployment" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
    
    if [ -z "$pod" ]; then
        log_warning "No pods found for $deployment, skipping health check"
        return 0
    fi
    
    while [ $attempt -le $max_attempts ]; do
        log_info "Health check attempt $attempt/$max_attempts..."
        
        # Check if pod is ready
        local ready=$(kubectl get pod "$pod" -n "$NAMESPACE" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "False")
        
        if [ "$ready" == "True" ]; then
            log_success "Health check passed for $deployment"
            return 0
        fi
        
        sleep 3
        ((attempt++))
    done
    
    log_error "Health check failed after $max_attempts attempts"
    return 1
}

create_slot_deployment() {
    local slot=$1
    local image="${IMAGE_REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"
    local deployment_name="${BASE_DEPLOYMENT}-${slot}"
    
    log_info "Creating/updating $slot deployment with image: $image"
    
    # Create/update the slot deployment
    cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ${deployment_name}
  namespace: ${NAMESPACE}
  labels:
    app.kubernetes.io/name: marketing
    app.kubernetes.io/component: marketing
    app.kubernetes.io/instance: codetether
    slot: ${slot}
spec:
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: marketing
      app.kubernetes.io/component: marketing
      slot: ${slot}
  template:
    metadata:
      labels:
        app.kubernetes.io/name: marketing
        app.kubernetes.io/component: marketing
        app.kubernetes.io/instance: codetether
        slot: ${slot}
    spec:
      containers:
      - name: marketing
        image: ${image}
        imagePullPolicy: Always
        ports:
        - containerPort: 3000
        env:
        - name: AUTH_TRUST_HOST
          value: "true"
        - name: AUTH_URL
          value: "https://codetether.run"
        - name: NEXTAUTH_URL
          value: "https://codetether.run"
        - name: NEXT_PUBLIC_API_URL
          value: "https://api.codetether.run"
        - name: KEYCLOAK_CLIENT_ID
          value: "a2a-monitor"
        - name: KEYCLOAK_ISSUER
          value: "https://auth.quantum-forge.io/realms/quantum-forge"
        envFrom:
        - secretRef:
            name: codetether-marketing-secrets
            optional: true
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            cpu: 500m
            memory: 512Mi
        readinessProbe:
          httpGet:
            path: /
            port: 3000
          initialDelaySeconds: 10
          periodSeconds: 5
        livenessProbe:
          httpGet:
            path: /
            port: 3000
          initialDelaySeconds: 30
          periodSeconds: 10
EOF

    log_success "Created deployment $deployment_name"
}

switch_traffic() {
    local target_slot=$1
    
    log_info "Switching traffic to $target_slot slot..."
    
    # Update service selector to point to the new slot
    kubectl patch svc "$SERVICE_NAME" -n "$NAMESPACE" --type='json' \
        -p="[{\"op\": \"replace\", \"path\": \"/spec/selector\", \"value\": {\"app.kubernetes.io/name\": \"marketing\", \"app.kubernetes.io/component\": \"marketing\", \"slot\": \"$target_slot\"}}]"
    
    log_success "Traffic switched to $target_slot"
}

cleanup_old_slot() {
    local old_slot=$1
    local deployment_name="${BASE_DEPLOYMENT}-${old_slot}"
    
    log_info "Cleaning up old $old_slot deployment..."
    
    # Scale down but don't delete (for quick rollback)
    kubectl scale deployment "$deployment_name" -n "$NAMESPACE" --replicas=0 2>/dev/null || true
    
    log_success "Old $old_slot deployment scaled to 0"
}

cleanup_original_deployment() {
    # Scale down the original non-blue-green deployment if it exists
    if kubectl get deployment "$BASE_DEPLOYMENT" -n "$NAMESPACE" &>/dev/null; then
        local replicas=$(kubectl get deployment "$BASE_DEPLOYMENT" -n "$NAMESPACE" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "0")
        if [ "$replicas" != "0" ]; then
            log_info "Scaling down original deployment $BASE_DEPLOYMENT..."
            kubectl scale deployment "$BASE_DEPLOYMENT" -n "$NAMESPACE" --replicas=0
            log_success "Original deployment scaled to 0"
        fi
    fi
}

deploy() {
    log_info "Starting blue-green deployment for marketing site..."
    
    local current_slot=$(get_current_slot)
    local new_slot=$(get_inactive_slot)
    
    log_info "Current active slot: ${current_slot:-none}"
    log_info "Deploying to slot: $new_slot"
    
    # Create/update the new slot deployment
    create_slot_deployment "$new_slot"
    
    # Wait for deployment to be ready
    if ! check_deployment_ready "${BASE_DEPLOYMENT}-${new_slot}" 180; then
        log_error "Deployment failed, aborting"
        return 1
    fi
    
    # Run health checks
    if ! health_check "$new_slot"; then
        log_error "Health check failed, aborting"
        return 1
    fi
    
    # Switch traffic
    switch_traffic "$new_slot"
    
    # Cleanup old slot (scale to 0)
    if [ "$current_slot" != "none" ] && [ "$current_slot" != "$new_slot" ]; then
        cleanup_old_slot "$current_slot"
    fi
    
    # Cleanup original non-blue-green deployment
    cleanup_original_deployment
    
    log_success "Blue-green deployment complete! Traffic now on $new_slot"
    
    # Show status
    status
}

rollback() {
    log_info "Rolling back marketing site..."
    
    local current_slot=$(get_current_slot)
    local old_slot=$(get_inactive_slot)
    local old_deployment="${BASE_DEPLOYMENT}-${old_slot}"
    
    log_info "Current slot: $current_slot"
    log_info "Rolling back to: $old_slot"
    
    # Check if old deployment exists
    if ! kubectl get deployment "$old_deployment" -n "$NAMESPACE" &>/dev/null; then
        log_error "No previous deployment found at $old_slot"
        return 1
    fi
    
    # Scale up old deployment
    kubectl scale deployment "$old_deployment" -n "$NAMESPACE" --replicas=1
    
    # Wait for it to be ready
    if ! check_deployment_ready "$old_deployment" 120; then
        log_error "Rollback deployment failed to start"
        return 1
    fi
    
    # Switch traffic back
    switch_traffic "$old_slot"
    
    # Scale down current (failed) slot
    cleanup_old_slot "$current_slot"
    
    log_success "Rollback complete! Traffic now on $old_slot"
}

status() {
    echo ""
    log_info "=== Marketing Site Blue-Green Status ==="
    echo ""
    
    local current_slot=$(get_current_slot)
    echo -e "Active slot: ${GREEN}${current_slot}${NC}"
    echo ""
    
    echo "Deployments:"
    kubectl get deployments -n "$NAMESPACE" -l "app.kubernetes.io/name=marketing" -o wide 2>/dev/null || echo "No deployments found"
    echo ""
    
    echo "Pods:"
    kubectl get pods -n "$NAMESPACE" -l "app.kubernetes.io/name=marketing" -o wide 2>/dev/null || echo "No pods found"
    echo ""
    
    echo "Service selector:"
    kubectl get svc "$SERVICE_NAME" -n "$NAMESPACE" -o jsonpath='{.spec.selector}' 2>/dev/null || echo "Service not found"
    echo ""
}

# Main
case "${1:-deploy}" in
    deploy)
        deploy
        ;;
    rollback)
        rollback
        ;;
    status)
        status
        ;;
    *)
        echo "Usage: $0 [deploy|rollback|status]"
        exit 1
        ;;
esac
