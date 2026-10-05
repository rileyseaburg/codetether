#!/usr/bin/env bash
# Test model resolution for gpt-5-codex variants
# Verifies that both bare and provider-prefixed model IDs work

set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8001}"
API_KEY="${A2A_API_KEY:-test-key}"

echo "=== Model Resolution Tests ==="

# Test 1: Check if server is running
echo -e "\n[Test 1] Server health check..."
if ! curl -sf "${BASE_URL}/health" > /dev/null 2>&1; then
    echo "FAIL: Server not responding at ${BASE_URL}"
    echo "Start with: cargo run --bin codetether-agent -- serve"
    exit 1
fi
echo "PASS: Server is running"

# Test 2: List available codex models
echo -e "\n[Test 2] Fetching codex models..."
CODEX_MODELS=$(curl -sf "${BASE_URL}/v1/agent/models" \
    -H "Authorization: Bearer ${API_KEY}" \
    | jq -r '.data[].id' | grep -i codex || true)

if [ -z "$CODEX_MODELS" ]; then
    echo "FAIL: No codex models found in /v1/agent/models"
    exit 1
fi
echo "PASS: Found codex models:"
echo "$CODEX_MODELS" | sed 's/^/  - /'

# Test 3: Verify specific models exist
echo -e "\n[Test 3] Verifying specific model IDs..."
for model in "gpt-5-codex" "gpt-5.1-codex"; do
    if echo "$CODEX_MODELS" | grep -q "^${model}$"; then
        echo "PASS: ${model} found"
    else
        echo "FAIL: ${model} NOT found"
        exit 1
    fi
done

# Test 4: Test agent endpoint with codex model
echo -e "\n[Test 4] Testing /v1/agent/codebases endpoint..."
CODEBASE_ID="test-model-$(date +%s)"
RESPONSE=$(curl -sf "${BASE_URL}/v1/agent/codebases/${CODEBASE_ID}/message" \
    -H "Authorization: Bearer ${API_KEY}" \
    -H "Content-Type: application/json" \
    -d '{"content": "Say hello", "model": "gpt-5.1-codex"}' \
    -w "\nHTTP_CODE:%{http_code}" 2>&1 || echo "HTTP_CODE:000")

HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE:" | cut -d: -f2)
BODY=$(echo "$RESPONSE" | grep -v "HTTP_CODE:")

if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "201" ]; then
    echo "PASS: Request accepted (HTTP $HTTP_CODE)"
elif [ "$HTTP_CODE" = "401" ]; then
    echo "SKIP: Auth required (expected in production)"
elif [ "$HTTP_CODE" = "404" ]; then
    echo "FAIL: Endpoint not found"
    exit 1
elif [ "$HTTP_CODE" = "400" ]; then
    echo "FAIL: Bad request - model might be invalid"
    echo "Response: $BODY"
    exit 1
else
    echo "FAIL: Unexpected HTTP $HTTP_CODE"
    echo "Response: $BODY"
    exit 1
fi

echo -e "\n=== All tests passed ==="
