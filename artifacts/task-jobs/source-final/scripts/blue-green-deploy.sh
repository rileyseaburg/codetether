#!/bin/bash
set -e

# CodeTether Blue-Green Deployment Script
# Usage: ./blue-green-deploy.sh [blue|green] [version]

NAMESPACE="a2a-server"
RELEASE_NAME="codetether"
CHART="oci://registry.quantum-forge.net/library/a2a-server"
VALUES_FILE="/home/riley/A2A-Server-MCP/chart/codetether-values.yaml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
TARGET_ENV="${1:-blue}"
VERSION="${2:-latest}"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  CodeTether Blue-Green Deployment${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Determine current and target environments
get_current_env() {
    local current=$(kubectl get ingress -n $NAMESPACE -o jsonpath='{.items[?(@.metadata.name=="codetether-active")].metadata.labels.environment}' 2>/dev/null || echo "none")
    if [ "$current" == "" ] || [ "$current" == "none" ]; then
        # Check which deployment is currently active by looking at the service selector
        local selector=$(kubectl get svc codetether-active -n $NAMESPACE -o jsonpath='{.spec.selector.slot}' 2>/dev/null || echo "blue")
        echo "${selector:-blue}"
    else
        echo "$current"
    fi
}

CURRENT_ENV=$(get_current_env)
if [ "$CURRENT_ENV" == "blue" ]; then
    INACTIVE_ENV="green"
else
    INACTIVE_ENV="blue"
fi

echo -e "Current active environment: ${GREEN}$CURRENT_ENV${NC}"
echo -e "Target deployment environment: ${BLUE}$TARGET_ENV${NC}"
echo -e "Version: ${YELLOW}$VERSION${NC}"
echo ""

# Function to deploy to a slot
deploy_slot() {
    local slot=$1
    local version=$2

    echo -e "${YELLOW}Deploying to $slot slot...${NC}"

    helm upgrade --install "${RELEASE_NAME}-${slot}" "$CHART" \
        --version "$version" \
        --namespace "$NAMESPACE" \
        --create-namespace \
        -f "$VALUES_FILE" \
        --set fullnameOverride="${RELEASE_NAME}-${slot}" \
        --set slot="$slot" \
        --set marketing.ingress.enabled=false \
        --set docs.ingress.enabled=false \
        --set ingress.enabled=false \
        --wait \
        --timeout 5m

    echo -e "${GREEN}Deployed to $slot slot successfully${NC}"
}

# Function to run health checks
health_check() {
    local slot=$1
    local service="${RELEASE_NAME}-${slot}-a2a-server"
    local max_attempts=30
    local attempt=1

    echo -e "${YELLOW}Running health checks on $slot...${NC}"

    while [ $attempt -le $max_attempts ]; do
        # Check pod readiness
        local ready=$(kubectl get pods -n $NAMESPACE -l "app.kubernetes.io/instance=${RELEASE_NAME}-${slot}" -o jsonpath='{.items[*].status.conditions[?(@.type=="Ready")].status}' 2>/dev/null)

        if [[ "$ready" == *"True"* ]]; then
            echo -e "${GREEN}Health check passed for $slot (attempt $attempt)${NC}"
            return 0
        fi

        echo "Waiting for $slot to be ready... (attempt $attempt/$max_attempts)"
        sleep 5
        ((attempt++))
    done

    echo -e "${RED}Health check failed for $slot${NC}"
    return 1
}

# Function to switch traffic
switch_traffic() {
    local target_slot=$1

    echo -e "${YELLOW}Switching traffic to $target_slot...${NC}"

    # Update the active service to point to the new slot
    kubectl patch svc codetether-active -n $NAMESPACE \
        -p "{\"spec\":{\"selector\":{\"slot\":\"$target_slot\"}}}" 2>/dev/null || \
    kubectl apply -f - <<EOF
apiVersion: v1
kind: Service
metadata:
  name: codetether-active
  namespace: $NAMESPACE
  labels:
    app: codetether
spec:
  selector:
    app.kubernetes.io/name: a2a-server
    slot: $target_slot
  ports:
    - name: http
      port: 8000
      targetPort: 8000
    - name: mcp
      port: 9000
      targetPort: 9000
    - name: marketing
      port: 3000
      targetPort: 3000
EOF

    # Update ingresses to point to active service
    kubectl apply -f - <<EOF
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: codetether-active-ingress
  namespace: $NAMESPACE
  labels:
    environment: $target_slot
  annotations:
    cert-manager.io/cluster-issuer: cloudflare-issuer
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/proxy-body-size: "50m"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "3600"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "3600"
spec:
  ingressClassName: nginx
  rules:
  - host: codetether.run
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: codetether-active
            port:
              number: 3000
  - host: www.codetether.run
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: codetether-active
            port:
              number: 3000
  - host: api.codetether.run
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: codetether-active
            port:
              number: 8000
      - path: /mcp
        pathType: Prefix
        backend:
          service:
            name: codetether-active
            port:
              number: 9000
  - host: docs.codetether.run
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: codetether-active
            port:
              number: 80
  tls:
  - hosts:
    - codetether.run
    - www.codetether.run
    secretName: codetether-run-tls
  - hosts:
    - api.codetether.run
    secretName: codetether-api-tls
  - hosts:
    - docs.codetether.run
    secretName: codetether-docs-tls
EOF

    echo -e "${GREEN}Traffic switched to $target_slot${NC}"
}

# Function to rollback
rollback() {
    local rollback_to=$1
    echo -e "${YELLOW}Rolling back to $rollback_to...${NC}"
    switch_traffic "$rollback_to"
    echo -e "${GREEN}Rollback complete${NC}"
}

# Function to cleanup old deployment
cleanup_old() {
    local old_slot=$1
    echo -e "${YELLOW}Cleaning up $old_slot deployment...${NC}"
    helm uninstall "${RELEASE_NAME}-${old_slot}" -n $NAMESPACE 2>/dev/null || true
    echo -e "${GREEN}Cleanup complete${NC}"
}

# Main deployment flow
main() {
    case "${3:-deploy}" in
        deploy)
            echo -e "${BLUE}Starting blue-green deployment...${NC}"
            echo ""

            # Step 1: Deploy to target slot
            deploy_slot "$TARGET_ENV" "$VERSION"
            echo ""

            # Step 2: Health check
            if ! health_check "$TARGET_ENV"; then
                echo -e "${RED}Deployment failed health checks. Aborting.${NC}"
                exit 1
            fi
            echo ""

            # Step 3: Switch traffic
            switch_traffic "$TARGET_ENV"
            echo ""

            echo -e "${GREEN}========================================${NC}"
            echo -e "${GREEN}  Deployment Complete!${NC}"
            echo -e "${GREEN}========================================${NC}"
            echo ""
            echo -e "Active environment: ${GREEN}$TARGET_ENV${NC}"
            echo -e "Previous environment: ${YELLOW}$CURRENT_ENV${NC} (kept for rollback)"
            echo ""
            echo "To rollback: $0 $CURRENT_ENV $VERSION rollback"
            echo "To cleanup old: $0 $CURRENT_ENV $VERSION cleanup"
            ;;

        rollback)
            rollback "$TARGET_ENV"
            ;;

        cleanup)
            cleanup_old "$TARGET_ENV"
            ;;

        status)
            echo -e "${BLUE}Current Status:${NC}"
            echo ""
            echo "Active slot: $(get_current_env)"
            echo ""
            echo "Blue deployment:"
            helm status "${RELEASE_NAME}-blue" -n $NAMESPACE 2>/dev/null || echo "  Not deployed"
            echo ""
            echo "Green deployment:"
            helm status "${RELEASE_NAME}-green" -n $NAMESPACE 2>/dev/null || echo "  Not deployed"
            ;;

        *)
            echo "Usage: $0 [blue|green] [version] [deploy|rollback|cleanup|status]"
            echo ""
            echo "Commands:"
            echo "  deploy   - Deploy to the specified slot and switch traffic"
            echo "  rollback - Switch traffic back to the specified slot"
            echo "  cleanup  - Remove the specified slot deployment"
            echo "  status   - Show current deployment status"
            exit 1
            ;;
    esac
}

main "$@"
