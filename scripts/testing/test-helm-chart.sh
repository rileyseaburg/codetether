#!/bin/bash
set -e

echo "Testing A2A Server Helm Chart"
echo "==============================="

CHART_DIR="chart/a2a-server"
TEST_RELEASE="a2a-test"

# Check if helm is installed
if ! command -v helm &> /dev/null; then
    echo "Error: Helm is not installed"
    exit 1
fi

echo "1. Linting the Helm chart..."
helm lint $CHART_DIR

echo "2. Building dependencies..."
cd $CHART_DIR
helm dependency build
cd - > /dev/null

echo "3. Testing template rendering with default values..."
helm template $TEST_RELEASE $CHART_DIR > /tmp/test-default.yaml
echo "   ✓ Default values template rendered successfully"

echo "4. Testing template rendering with development values..."
helm template $TEST_RELEASE $CHART_DIR \
  --values $CHART_DIR/examples/values-dev.yaml > /tmp/test-dev.yaml
echo "   ✓ Development values template rendered successfully"

echo "5. Testing template rendering with staging values..."
helm template $TEST_RELEASE $CHART_DIR \
  --values $CHART_DIR/examples/values-staging.yaml > /tmp/test-staging.yaml
echo "   ✓ Staging values template rendered successfully"

echo "6. Testing template rendering with production values..."
helm template $TEST_RELEASE $CHART_DIR \
  --values $CHART_DIR/examples/values-prod.yaml > /tmp/test-prod.yaml
echo "   ✓ Production values template rendered successfully"

echo "7. Testing Redis disabled configuration..."
helm template $TEST_RELEASE $CHART_DIR \
  --set redis.enabled=false > /tmp/test-no-redis.yaml
echo "   ✓ External Redis configuration rendered successfully"

echo "8. Testing authentication enabled configuration..."
helm template $TEST_RELEASE $CHART_DIR \
  --set auth.enabled=true \
  --set auth.tokens.test-agent=test-token > /tmp/test-auth.yaml
echo "   ✓ Authentication configuration rendered successfully"

echo "9. Validating rendered manifests..."

# Check that essential resources are present
for template in /tmp/test-*.yaml; do
    echo "   Checking $template..."
    
    # Check for required resources
    if ! grep -q "kind: Deployment" "$template"; then
        echo "   ❌ Missing Deployment in $template"
        exit 1
    fi
    
    if ! grep -q "kind: Service" "$template"; then
        echo "   ❌ Missing Service in $template"
        exit 1
    fi
    
    if ! grep -q "kind: ConfigMap" "$template"; then
        echo "   ❌ Missing ConfigMap in $template"
        exit 1
    fi
    
    if ! grep -q "kind: ServiceAccount" "$template"; then
        echo "   ❌ Missing ServiceAccount in $template"
        exit 1
    fi
    
    echo "   ✓ Essential resources found in $template"
done

echo "10. Testing dry-run installation (if cluster available)..."
if kubectl version --client &>/dev/null && kubectl cluster-info &>/dev/null; then
    helm install $TEST_RELEASE $CHART_DIR \
      --values $CHART_DIR/examples/values-dev.yaml \
      --dry-run --debug > /tmp/test-dry-run.yaml 2>&1
    echo "   ✓ Dry-run installation completed successfully"
else
    echo "   ⚠ Skipping dry-run installation (no Kubernetes cluster available)"
    echo "   ✓ Template validation sufficient for chart verification"
fi

echo ""
echo "All tests passed! ✅"
echo ""
echo "Generated test files:"
ls -la /tmp/test-*.yaml

echo ""
echo "To clean up test files:"
echo "rm /tmp/test-*.yaml"

echo ""
echo "Chart validation completed successfully!"
echo "The A2A Server Helm chart is ready for deployment."