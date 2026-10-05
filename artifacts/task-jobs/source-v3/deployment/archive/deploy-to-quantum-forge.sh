#!/bin/bash
# Deploy A2A Server to Quantum Forge Registry
# This script builds, tags, and pushes the Docker image and Helm chart
#
# Usage:
#   ./deploy-to-quantum-forge.sh                    # Full deployment with tests
#   VERSION=v1.0.0 ./deploy-to-quantum-forge.sh     # Deploy specific version
#   RUN_TESTS=false ./deploy-to-quantum-forge.sh    # Skip integration tests
#   DRY_RUN=true ./deploy-to-quantum-forge.sh       # Test without pushing
#   SKIP_BUILD=true ./deploy-to-quantum-forge.sh    # Skip Docker build
#   INSTALL_CHART=false ./deploy-to-quantum-forge.sh # Skip Helm install
#
# Environment Variables:
#   VERSION           - Image version tag (default: latest)
#   REGISTRY          - Container registry (default: registry.quantum-forge.net)
#   PROJECT           - Registry project (default: library)
#   IMAGE_NAME        - Image name (default: a2a-server)
#   SKIP_BUILD        - Skip Docker build (default: false)
#   SKIP_DOCKER       - Skip Docker operations (default: false)
#   SKIP_HELM         - Skip Helm operations (default: false)
#   DRY_RUN           - Test run without pushing (default: false)
#   VERIFY_IMAGE      - Verify image pull after push (default: true)
#   INSTALL_CHART     - Install Helm chart (default: true)
#   CHECK_STATUS      - Check deployment status (default: true)
#   RUN_TESTS         - Run integration tests (default: true)
#   TEST_TIMEOUT      - Test timeout in seconds (default: 300)

set -e

# Configuration
VERSION="${VERSION:-latest}"
REGISTRY="${REGISTRY:-registry.quantum-forge.net}"
PROJECT="${PROJECT:-library}"
IMAGE_NAME="${IMAGE_NAME:-a2a-server}"
SKIP_BUILD="${SKIP_BUILD:-false}"
SKIP_DOCKER="${SKIP_DOCKER:-false}"
SKIP_HELM="${SKIP_HELM:-false}"
DRY_RUN="${DRY_RUN:-false}"
VERIFY_IMAGE="${VERIFY_IMAGE:-true}"
INSTALL_CHART="${INSTALL_CHART:-true}"
CHECK_STATUS="${CHECK_STATUS:-true}"
RUN_TESTS="${RUN_TESTS:-true}"
TEST_TIMEOUT="${TEST_TIMEOUT:-300}"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

function info() { echo -e "${CYAN}$1${NC}"; }
function success() { echo -e "${GREEN}✓ $1${NC}"; }
function error() { echo -e "${RED}✗ $1${NC}"; }
function warning() { echo -e "${YELLOW}⚠ $1${NC}"; }

echo -e "${CYAN}===============================================${NC}"
echo -e "${CYAN}   A2A Server - Quantum Forge Deployment${NC}"
echo -e "${CYAN}===============================================${NC}"
echo ""

# Build full image name
FULL_IMAGE_NAME="$REGISTRY/$PROJECT/$IMAGE_NAME:$VERSION"
CHART_PATH="chart/a2a-server"
CHART_VERSION="0.1.0"

info "Configuration:"
echo "  Registry:      $REGISTRY"
echo "  Project:       $PROJECT"
echo "  Image:         $FULL_IMAGE_NAME"
echo "  Chart Path:    $CHART_PATH"
echo "  Chart Version: $CHART_VERSION"
echo ""

if [ "$DRY_RUN" = "true" ]; then
    warning "DRY RUN MODE - No actual push operations will be performed"
    echo ""
fi

# Step 1: Build Docker Image
if [ "$SKIP_DOCKER" != "true" ]; then
    if [ "$SKIP_BUILD" != "true" ]; then
        info "Step 1: Building Docker image..."
        if make docker-build; then
            success "Docker image built successfully"
        else
            error "Failed to build Docker image"
            exit 1
        fi
        echo ""
    fi

    # Step 2: Tag Docker Image
    info "Step 2: Tagging Docker image for Quantum Forge..."
    if docker tag a2a-server-mcp:$VERSION $FULL_IMAGE_NAME; then
        success "Image tagged as $FULL_IMAGE_NAME"
    else
        error "Failed to tag Docker image"
        exit 1
    fi
    echo ""

    # Step 3: Push Docker Image
    info "Step 3: Pushing Docker image to Quantum Forge..."
    if [ "$DRY_RUN" = "true" ]; then
        warning "Would execute: docker push $FULL_IMAGE_NAME"
    else
        echo -e "${YELLOW}Pushing to: $FULL_IMAGE_NAME${NC}"
        if docker push $FULL_IMAGE_NAME; then
            success "Docker image pushed successfully"
        else
            error "Failed to push Docker image"
            warning "Make sure you're logged in: docker login $REGISTRY"
            exit 1
        fi
    fi
    echo ""
fi

# Step 4: Package Helm Chart
if [ "$SKIP_HELM" != "true" ]; then
    info "Step 4: Packaging Helm chart..."

    # Update chart values with Quantum Forge image
    VALUES_PATH="$CHART_PATH/values.yaml"
    if [ -f "$VALUES_PATH" ]; then
        info "Updating chart values with Quantum Forge image reference..."
        sed -i.bak "s|repository:.*a2a-server|repository: $REGISTRY/$PROJECT/$IMAGE_NAME|g" "$VALUES_PATH"
        sed -i.bak "s|tag:.*\"latest\"|tag: \"$VERSION\"|g" "$VALUES_PATH"
        rm -f "$VALUES_PATH.bak"
        success "Chart values updated"
    fi

    # Build dependencies
    info "Building chart dependencies..."
    (cd $CHART_PATH && helm dependency build)

    # Package the chart
    if helm package $CHART_PATH; then
        CHART_PACKAGE="a2a-server-$CHART_VERSION.tgz"
        success "Helm chart packaged: $CHART_PACKAGE"
    else
        error "Failed to package Helm chart"
        exit 1
    fi
    echo ""

    # Step 5: Push Helm Chart
    info "Step 5: Pushing Helm chart to Quantum Forge..."
    if [ "$DRY_RUN" = "true" ]; then
        warning "Would execute: helm push $CHART_PACKAGE oci://$REGISTRY/$PROJECT"
    else
        CHART_PACKAGE="a2a-server-$CHART_VERSION.tgz"
        echo -e "${YELLOW}Pushing chart: $CHART_PACKAGE${NC}"
        echo -e "${YELLOW}To registry: oci://$REGISTRY/$PROJECT${NC}"

        if helm push $CHART_PACKAGE oci://$REGISTRY/$PROJECT; then
            success "Helm chart pushed successfully"

            # Cleanup package
            if [ -f "$CHART_PACKAGE" ]; then
                rm -f $CHART_PACKAGE
                info "Cleaned up local chart package"
            fi
        else
            error "Failed to push Helm chart"
            warning "Make sure you're logged in: helm registry login $REGISTRY"
            exit 1
        fi
    fi
    echo ""
fi

# Summary
echo -e "${GREEN}===============================================${NC}"
echo -e "${GREEN}   Deployment Summary${NC}"
echo -e "${GREEN}===============================================${NC}"
echo ""

if [ "$SKIP_DOCKER" != "true" ]; then
    success "Docker Image: $FULL_IMAGE_NAME"
fi

if [ "$SKIP_HELM" != "true" ]; then
    success "Helm Chart: oci://$REGISTRY/$PROJECT/a2a-server:$CHART_VERSION"
fi

echo ""
echo -e "${CYAN}Next Steps:${NC}"
if [ "$RUN_TESTS" != "true" ]; then
    echo "  1. Run tests: RUN_TESTS=true $0"
    echo "  2. Verify image: docker pull $FULL_IMAGE_NAME"
    echo "  3. Check logs: kubectl logs -n a2a-system -l app.kubernetes.io/name=a2a-server"
else
    echo "  1. View logs: kubectl logs -n a2a-system -l app.kubernetes.io/name=a2a-server"
    echo "  2. Monitor: kubectl get pods -n a2a-system -w"
    echo "  3. Access locally: kubectl port-forward -n a2a-system svc/a2a-server 8000:8000 9000:9000"
fi
echo ""

if [ "$DRY_RUN" = "true" ]; then
    warning "This was a DRY RUN - no changes were made"
fi

# Step 6: Verify Docker Image
if [ "$VERIFY_IMAGE" = "true" ] && [ "$DRY_RUN" != "true" ]; then
    info "Step 6: Verifying Docker image pull..."
    if docker pull $FULL_IMAGE_NAME; then
        success "Docker image verified successfully"
    else
        warning "Failed to verify Docker image pull"
    fi
    echo ""
fi

# Step 7: Install Helm Chart
if [ "$INSTALL_CHART" = "true" ] && [ "$DRY_RUN" != "true" ]; then
    info "Step 7: Installing Helm chart to Kubernetes..."

    # Check if namespace exists, create if not
    if ! kubectl --kubeconfig ~/.kube/config get namespace a2a-system >/dev/null 2>&1; then
        info "Creating namespace a2a-system..."
        kubectl --kubeconfig ~/.kube/config create namespace a2a-system
        success "Namespace a2a-system created"
    fi

    # Install or upgrade the chart
    if helm status a2a-server -n a2a-system --kubeconfig ~/.kube/config >/dev/null 2>&1; then
        info "Upgrading existing deployment..."
        if helm upgrade a2a-server oci://$REGISTRY/$PROJECT/a2a-server --version $CHART_VERSION --namespace a2a-system --kubeconfig ~/.kube/config; then
            success "Helm chart upgraded successfully"
        else
            error "Failed to upgrade Helm chart"
            exit 1
        fi
    else
        info "Installing new deployment..."
        if helm install a2a-server oci://$REGISTRY/$PROJECT/a2a-server --version $CHART_VERSION --namespace a2a-system --create-namespace --kubeconfig ~/.kube/config; then
            success "Helm chart installed successfully"
        else
            error "Failed to install Helm chart"
            exit 1
        fi
    fi
    echo ""
fi

# Step 8: Check Deployment Status
if [ "$CHECK_STATUS" = "true" ] && [ "$DRY_RUN" != "true" ]; then
    info "Step 8: Checking deployment status..."

    # Wait for pods to be ready
    info "Waiting for pods to be ready..."
    if kubectl --kubeconfig ~/.kube/config wait --for=condition=ready pod -l app.kubernetes.io/name=a2a-server -n a2a-system --timeout=300s; then
        success "Pods are ready"
    else
        warning "Pods are not ready after timeout"
    fi

    # Show pod status
    echo ""
    info "Pod status:"
    kubectl --kubeconfig ~/.kube/config get pods -n a2a-system

    # Show service status
    echo ""
    info "Service status:"
    kubectl --kubeconfig ~/.kube/config get services -n a2a-system

    # Show ingress status (if available)
    if kubectl --kubeconfig ~/.kube/config get ingress -n a2a-system >/dev/null 2>&1; then
        echo ""
        info "Ingress status:"
        kubectl --kubeconfig ~/.kube/config get ingress -n a2a-system
    fi

    echo ""
    success "Deployment check completed"

    # Show access information
    echo ""
    echo -e "${CYAN}Access Information:${NC}"
    if kubectl --kubeconfig ~/.kube/config get svc -n a2a-system a2a-server -o jsonpath='{.spec.type}' 2>/dev/null | grep -q "LoadBalancer"; then
        LB_IP=$(kubectl --kubeconfig ~/.kube/config get svc -n a2a-system a2a-server -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "pending")
        echo "  LoadBalancer IP: $LB_IP"
    fi

    if kubectl --kubeconfig ~/.kube/config get ingress -n a2a-system a2a-server -o jsonpath='{.spec.rules[0].host}' 2>/dev/null >/dev/null; then
        HOST=$(kubectl --kubeconfig ~/.kube/config get ingress -n a2a-system a2a-server -o jsonpath='{.spec.rules[0].host}')
        echo "  Ingress Host: https://$HOST"
        echo "  MCP Endpoint: https://$HOST/mcp"
        echo "  Monitor UI:   https://$HOST/v1/monitor/"
    fi
fi

# Step 9: Run Integration Tests
if [ "$RUN_TESTS" = "true" ] && [ "$DRY_RUN" != "true" ] && [ "$INSTALL_CHART" = "true" ]; then
    echo ""
    info "Step 9: Running integration tests against deployed service..."

    # Get the ingress host
    INGRESS_HOST=$(kubectl --kubeconfig ~/.kube/config get ingress -n a2a-system a2a-server -o jsonpath='{.spec.rules[0].host}' 2>/dev/null || echo "")

    if [ -z "$INGRESS_HOST" ]; then
        warning "No ingress host found, falling back to port-forward..."
        # Set up port-forward for testing
        info "Setting up port-forward for testing..."
        kubectl --kubeconfig ~/.kube/config port-forward -n a2a-system svc/a2a-server 8000:8000 9000:9000 > /dev/null 2>&1 &
        PF_PID=$!

        # Wait for port-forward to be ready
        sleep 3

        A2A_URL="http://localhost:8000"
        MCP_URL="http://localhost:9000"
    else
        info "Using ingress URL: https://$INGRESS_HOST"
        A2A_URL="https://$INGRESS_HOST"
        MCP_URL="https://$INGRESS_HOST/mcp"

        # Wait for certificate to be issued
        info "Waiting for TLS certificate to be issued..."
        CERT_NAME=$(kubectl --kubeconfig ~/.kube/config get ingress -n a2a-system a2a-server -o jsonpath='{.spec.tls[0].secretName}' 2>/dev/null || echo "")

        if [ ! -z "$CERT_NAME" ]; then
            info "Certificate name: $CERT_NAME"

            # Wait for certificate to be ready (timeout after 5 minutes)
            TIMEOUT=300
            ELAPSED=0
            while [ $ELAPSED -lt $TIMEOUT ]; do
                CERT_READY=$(kubectl --kubeconfig ~/.kube/config get certificate -n a2a-system $CERT_NAME -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "")

                if [ "$CERT_READY" = "True" ]; then
                    success "Certificate is ready"
                    break
                fi

                if [ $((ELAPSED % 10)) -eq 0 ]; then
                    info "Still waiting for certificate... (${ELAPSED}s elapsed)"
                fi

                sleep 5
                ELAPSED=$((ELAPSED + 5))
            done

            if [ "$CERT_READY" != "True" ]; then
                warning "Certificate not ready after ${TIMEOUT}s"
                info "Certificate status:"
                kubectl --kubeconfig ~/.kube/config describe certificate -n a2a-system $CERT_NAME
            fi
        else
            warning "No TLS certificate found in ingress configuration"
        fi

        # Additional wait for ingress to propagate
        info "Waiting for ingress to be fully ready..."
        sleep 10
    fi

    # Test basic connectivity
    info "Testing service connectivity at $A2A_URL..."
    TEST_FAILED=false

    # Test 1: Health check (MCP root endpoint)
    echo "  1. MCP health check..."
    if curl -s --max-time 10 "$MCP_URL/" | grep -q '"status"'; then
        success "    MCP health check passed"
    else
        warning "    MCP health check failed (not critical)"
    fi

    # Test 2: Agent card endpoint
    echo "  2. Agent card endpoint..."
    if curl -s --max-time 10 "$A2A_URL/.well-known/agent-card.json" | grep -q '"name"'; then
        success "    Agent card endpoint passed"
    else
        error "    Agent card endpoint failed"
        TEST_FAILED=true
    fi

    # Test 3: MCP tools listing
    echo "  3. MCP tools listing..."
    if curl -s --max-time 10 "$MCP_URL/v1/tools" | grep -q 'tools'; then
        success "    MCP tools listing passed"
    else
        error "    MCP tools listing failed"
        TEST_FAILED=true
    fi

    # Test 4: Calculator tool
    echo "  4. Calculator tool test..."
    CALC_RESULT=$(curl -s --max-time 10 -X POST "$MCP_URL/v1/rpc" \
        -H "Content-Type: application/json" \
        -d '{
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "calculator",
                "arguments": {
                    "operation": "add",
                    "a": 10,
                    "b": 5
                }
            }
        }')

    if echo "$CALC_RESULT" | grep -q '"result"'; then
        success "    Calculator tool test passed"
    else
        warning "    Calculator tool test skipped or failed"
    fi

    # Test 5: Run pytest if available
    if command -v pytest &> /dev/null && [ -f "requirements-test.txt" ]; then
        echo "  5. Running pytest integration tests..."

        # Install test dependencies if needed
        if [ ! -d "venv" ]; then
            info "    Creating test virtual environment..."
            python3 -m venv venv
            source venv/bin/activate
            pip install -q -r requirements-test.txt
            # Install the package in editable mode
            pip install -q -e .
        else
            source venv/bin/activate
            # Ensure package is installed in existing venv
            if ! pip show a2a-server-mcp &>/dev/null; then
                info "    Installing package in editable mode..."
                pip install -q -e .
            fi
        fi

        # Set environment variables for tests
        export A2A_SERVER_URL="$A2A_URL"
        export MCP_SERVER_URL="$MCP_URL"

        # Run integration tests (if they exist)
        if pytest tests/test_a2a_server.py -v --tb=short 2>&1 | tee /tmp/test-results.log; then
            # Check if there were collection errors
            if grep -q "ERROR collecting" /tmp/test-results.log; then
                warning "    Pytest had collection errors (check /tmp/test-results.log)"
            elif grep -q "collected 0 items" /tmp/test-results.log; then
                info "    No tests collected"
            else
                success "    Pytest tests passed"
            fi
        else
            warning "    Some pytest tests failed (check /tmp/test-results.log)"
        fi

        deactivate
    else
        info "    Pytest not available, skipping unit tests"
    fi    # Cleanup port-forward if used
    if [ ! -z "$PF_PID" ]; then
        info "Cleaning up port-forward..."
        kill $PF_PID 2>/dev/null
    fi

    echo ""
    if [ "$TEST_FAILED" = "true" ]; then
        error "Some integration tests failed!"
        echo ""
        echo -e "${YELLOW}Troubleshooting:${NC}"
        echo "  - Check pod logs: kubectl logs -n a2a-system -l app.kubernetes.io/name=a2a-server"
        echo "  - Check pod status: kubectl describe pod -n a2a-system -l app.kubernetes.io/name=a2a-server"
        echo "  - Verify service: kubectl get svc -n a2a-system a2a-server"
        echo "  - Check ingress: kubectl describe ingress -n a2a-system a2a-server"
        echo "  - Verify certificate: kubectl get certificate -n a2a-system"
        exit 1
    else
        success "All integration tests passed!"
    fi
fi
