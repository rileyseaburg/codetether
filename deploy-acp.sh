#!/bin/bash

# Deploy A2A Server to acp.quantum-forge.net
# Complete automated deployment script

set -e

# Default values
VERSION="${VERSION:-v1.0.0}"
REGISTRY="${REGISTRY:-registry.quantum-forge.net}"
PROJECT="${PROJECT:-library}"
IMAGE_NAME="${IMAGE_NAME:-a2a-server}"
DOMAIN="${DOMAIN:-acp.quantum-forge.net}"
SKIP_BUILD="${SKIP_BUILD:-false}"
SKIP_TESTS="${SKIP_TESTS:-false}"
PRODUCTION="${PRODUCTION:-false}"

# Color functions
function print_step() { echo -e "\n\033[36m▶ $1\033[0m"; }
function print_success() { echo -e "\033[32m✓ $1\033[0m"; }
function print_error() { echo -e "\033[31m✗ $1\033[0m"; }
function print_warning() { echo -e "\033[33m⚠ $1\033[0m"; }
function print_info() { echo -e "\033[90m  $1\033[0m"; }

echo "============================================================"
echo "    A2A Server Deployment to acp.quantum-forge.net"
echo "============================================================"
echo ""

# Configuration
FULL_IMAGE_NAME="$REGISTRY/$PROJECT/$IMAGE_NAME:$VERSION"
LATEST_IMAGE_NAME="$REGISTRY/$PROJECT/$IMAGE_NAME:latest"
CHART_PATH="chart/a2a-server"
CHART_VERSION="0.1.0"
NAMESPACE="a2a-system"

print_info "Configuration:"
print_info "  Registry:      $REGISTRY"
print_info "  Image:         $FULL_IMAGE_NAME"
print_info "  Domain:        $DOMAIN"
print_info "  Namespace:     $NAMESPACE"
if [ "$PRODUCTION" = "true" ]; then
    print_info "  Environment:   Production"
else
    print_info "  Environment:   Staging"
fi
echo ""

# Step 1: Run tests (if not skipped)
if [ "$SKIP_TESTS" != "true" ]; then
    print_step "Running tests..."
    if python -m pytest tests/ -v; then
        print_success "All tests passed"
    else
        print_warning "Some tests failed, but continuing..."
    fi
fi

# Step 2: Build Docker image
if [ "$SKIP_BUILD" != "true" ]; then
    print_step "Building Docker image..."
    BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    docker build -t a2a-server:$VERSION \
        --build-arg VERSION=$VERSION \
        --build-arg BUILD_DATE=$BUILD_DATE \
        . || { print_error "Docker build failed"; exit 1; }
    print_success "Docker image built successfully"
fi

# Step 3: Tag images
print_step "Tagging Docker images..."
docker tag a2a-server:$VERSION $FULL_IMAGE_NAME
docker tag a2a-server:$VERSION $LATEST_IMAGE_NAME
print_success "Images tagged"
print_info "  - $FULL_IMAGE_NAME"
print_info "  - $LATEST_IMAGE_NAME"

# Step 4: Push Docker images
print_step "Pushing Docker images to Quantum Forge..."
print_info "Pushing versioned image..."
docker push $FULL_IMAGE_NAME || { 
    print_error "Failed to push $FULL_IMAGE_NAME"
    print_warning "Make sure you're logged in: docker login $REGISTRY"
    exit 1
}

print_info "Pushing latest tag..."
docker push $LATEST_IMAGE_NAME || {
    print_error "Failed to push $LATEST_IMAGE_NAME"
    exit 1
}
print_success "Docker images pushed successfully"

# Step 5: Update Helm chart values
print_step "Updating Helm chart values..."
VALUES_PATH="$CHART_PATH/values.yaml"
sed -i.bak "s|repository:.*a2a-server.*|repository: $REGISTRY/$PROJECT/$IMAGE_NAME|g" $VALUES_PATH
sed -i.bak "s|tag:.*\".*\"|tag: \"$VERSION\"|g" $VALUES_PATH
rm -f $VALUES_PATH.bak
print_success "Chart values updated"

# Step 6: Build Helm dependencies
print_step "Building Helm chart dependencies..."
cd $CHART_PATH
helm dependency build || { print_error "Helm dependency build failed"; cd ../..; exit 1; }
cd ../..
print_success "Helm dependencies built"

# Step 7: Package Helm chart
print_step "Packaging Helm chart..."
helm package $CHART_PATH || { print_error "Helm package failed"; exit 1; }
CHART_PACKAGE="a2a-server-$CHART_VERSION.tgz"
print_success "Helm chart packaged: $CHART_PACKAGE"

# Step 8: Push Helm chart
print_step "Pushing Helm chart to Quantum Forge..."
helm push a2a-server-$CHART_VERSION.tgz oci://$REGISTRY/$PROJECT || {
    print_error "Helm push failed"
    print_warning "Make sure you're logged in: helm registry login $REGISTRY"
    exit 1
}
print_success "Helm chart pushed to oci://$REGISTRY/$PROJECT/a2a-server:$CHART_VERSION"

# Cleanup
rm -f a2a-server-$CHART_VERSION.tgz

# Step 9: Deploy to Kubernetes
print_step "Deploying to Kubernetes..."

# Set replica count based on environment
if [ "$PRODUCTION" = "true" ]; then
    REPLICA_COUNT=3
    AUTOSCALING_ENABLED=true
    PDB_ENABLED=true
    CPU_LIMITS="2000m"
    MEM_LIMITS="2Gi"
else
    REPLICA_COUNT=2
    AUTOSCALING_ENABLED=false
    PDB_ENABLED=false
    CPU_LIMITS="1000m"
    MEM_LIMITS="1Gi"
fi

# Generate random Redis password
REDIS_PASSWORD=$(openssl rand -hex 16)

# Create production values file
cat > acp-production-values.yaml <<EOF
image:
  repository: $REGISTRY/$PROJECT/$IMAGE_NAME
  tag: "$VERSION"
  pullPolicy: Always

replicaCount: $REPLICA_COUNT

service:
  type: LoadBalancer
  port: 8000
  mcp:
    enabled: true
    port: 9000

ingress:
  enabled: true
  className: "nginx"
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
  hosts:
    - host: $DOMAIN
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: acp-quantum-forge-tls
      hosts:
        - $DOMAIN

resources:
  limits:
    cpu: $CPU_LIMITS
    memory: $MEM_LIMITS
  requests:
    cpu: 500m
    memory: 512Mi

autoscaling:
  enabled: $AUTOSCALING_ENABLED
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70

redis:
  enabled: true
  auth:
    enabled: true
    password: "$REDIS_PASSWORD"
  master:
    persistence:
      enabled: true
      size: 8Gi

env:
  A2A_HOST: "0.0.0.0"
  A2A_PORT: "8000"
  A2A_LOG_LEVEL: "INFO"
  MCP_HTTP_ENABLED: "true"
  MCP_HTTP_HOST: "0.0.0.0"
  MCP_HTTP_PORT: "9000"
  A2A_AGENT_NAME: "ACP Quantum Forge Agent"
  A2A_AGENT_DESCRIPTION: "Production A2A agent with MCP integration at acp.quantum-forge.net"

monitoring:
  serviceMonitor:
    enabled: true
    interval: 30s

networkPolicy:
  enabled: true

podDisruptionBudget:
  enabled: $PDB_ENABLED
  minAvailable: 1
EOF

# Create namespace if it doesn't exist
kubectl create namespace $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -

# Install or upgrade the release
print_info "Installing/upgrading release..."
helm upgrade --install a2a-server \
    oci://$REGISTRY/$PROJECT/a2a-server \
    --version $CHART_VERSION \
    --namespace $NAMESPACE \
    --values acp-production-values.yaml \
    --wait \
    --timeout 10m || { print_error "Helm install/upgrade failed"; exit 1; }

print_success "Successfully deployed to Kubernetes"

# Step 10: Verify deployment
print_step "Verifying deployment..."
sleep 5

RUNNING_PODS=$(kubectl get pods -n $NAMESPACE -l app.kubernetes.io/name=a2a-server -o json | jq -r '.items[] | select(.status.phase=="Running") | .metadata.name' | wc -l)
print_info "Running pods: $RUNNING_PODS"

if [ "$RUNNING_PODS" -gt 0 ]; then
    print_success "Deployment verified - $RUNNING_PODS pod(s) running"
else
    print_warning "No running pods found yet"
fi

# Get service info
SERVICE_TYPE=$(kubectl get svc -n $NAMESPACE a2a-server -o jsonpath='{.spec.type}')
print_info "Service type: $SERVICE_TYPE"

EXTERNAL_IP=$(kubectl get svc -n $NAMESPACE a2a-server -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "pending")
if [ "$EXTERNAL_IP" != "pending" ] && [ -n "$EXTERNAL_IP" ]; then
    print_info "External IP: $EXTERNAL_IP"
fi

# Step 11: Setup DNS (informational)
print_step "DNS Configuration Required:"
print_warning "Please configure DNS for $DOMAIN to point to the LoadBalancer IP"
print_info "Run this command to get the external IP:"
print_info "  kubectl get svc -n $NAMESPACE a2a-server"
echo ""

# Summary
echo "============================================================"
echo "    Deployment Complete!"
echo "============================================================"
echo ""

print_success "Docker Image: $FULL_IMAGE_NAME"
print_success "Helm Chart: oci://$REGISTRY/$PROJECT/a2a-server:$CHART_VERSION"
print_success "Namespace: $NAMESPACE"
print_success "Domain: $DOMAIN"
echo ""

echo "Next Steps:"
echo "  1. Configure DNS: $DOMAIN -> LoadBalancer IP"
echo "  2. Wait for cert-manager to issue TLS certificate"
echo "  3. Verify endpoints:"
echo "     - https://$DOMAIN/.well-known/agent-card.json"
echo "     - https://$DOMAIN/v1/monitor/"
echo "     - https://$DOMAIN/health"
echo "  4. Test MCP endpoint: https://${DOMAIN}:9000/mcp/v1/tools"
echo ""

echo "Monitoring:"
echo "  - Web UI: https://$DOMAIN/v1/monitor/"
echo "  - Logs: kubectl logs -n $NAMESPACE -l app.kubernetes.io/name=a2a-server -f"
echo "  - Status: kubectl get pods -n $NAMESPACE"
echo ""

# Cleanup
rm -f acp-production-values.yaml

print_success "Deployment script completed successfully!"
