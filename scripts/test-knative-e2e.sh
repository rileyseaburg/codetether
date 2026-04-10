#!/bin/bash
#
# End-to-End Test for Knative CodeTether Workers
#
# This script tests the FULL flow:
# 1. Trigger agent via API
# 2. Verify Knative Service is created
# 3. Verify worker pod starts
# 4. Wait for task to complete
# 5. Verify task output
# 6. Cleanup
#
# Usage:
#   ./scripts/test-knative-e2e.sh [--no-cleanup] [--codebase-id ID]
#

set -e

# Configuration
API_URL="${API_URL:-https://api.codetether.run}"
NAMESPACE="a2a-server"
CLEANUP=true
TIMEOUT=300
POLL_INTERVAL=5
CODEBASE_ID=""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --no-cleanup) CLEANUP=false; shift ;;
        --codebase-id) CODEBASE_ID="$2"; shift 2 ;;
        --timeout) TIMEOUT="$2"; shift 2 ;;
        -h|--help)
            echo "Usage: $0 [--no-cleanup] [--codebase-id ID] [--timeout SECONDS]"
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_error() { echo -e "${RED}[FAIL]${NC} $1"; }
log_step() { echo -e "\n${CYAN}=== $1 ===${NC}"; }

cleanup() {
    if [ "$CLEANUP" = true ] && [ -n "$SESSION_ID" ]; then
        log_info "Cleaning up Knative resources..."
        kubectl delete ksvc "codetether-session-${SESSION_ID}" -n "$NAMESPACE" 2>/dev/null || true
        kubectl delete trigger "trigger-session-${SESSION_ID}" -n "$NAMESPACE" 2>/dev/null || true
    fi
}
trap cleanup EXIT

# Get codebase
log_step "Setup"
if [ -z "$CODEBASE_ID" ]; then
    CODEBASE_ID=$(curl -s "${API_URL}/v1/agent/codebases" | jq -r '.[0].id')
fi
log_info "Using codebase: $CODEBASE_ID"

# Trigger agent
log_step "1. Triggering Agent"
TRIGGER_RESPONSE=$(curl -s -X POST "${API_URL}/v1/agent/codebases/${CODEBASE_ID}/trigger" \
    -H "Content-Type: application/json" \
    -d '{"prompt": "What is 2+2? Reply with ONLY the number, nothing else.", "agent": "code", "model": ""}')

echo "$TRIGGER_RESPONSE" | jq .

# Extract IDs
KNATIVE_FLAG=$(echo "$TRIGGER_RESPONSE" | jq -r '.knative // false')
SESSION_ID=$(echo "$TRIGGER_RESPONSE" | jq -r '.session_id // empty')
TASK_ID=$(echo "$TRIGGER_RESPONSE" | jq -r '.message' | grep -oP 'task: \K[a-f0-9-]+' || echo "")

if [ "$KNATIVE_FLAG" != "true" ]; then
    log_error "Knative path was NOT used! Response:"
    echo "$TRIGGER_RESPONSE" | jq .
    exit 1
fi
log_success "Knative path used, session: $SESSION_ID"

if [ -z "$TASK_ID" ]; then
    log_error "Could not extract task ID from response"
    exit 1
fi
log_info "Task ID: $TASK_ID"

# Wait for Knative Service
log_step "2. Waiting for Knative Service"
KSVC_NAME="codetether-session-${SESSION_ID}"
START=$(date +%s)

while true; do
    ELAPSED=$(($(date +%s) - START))
    [ $ELAPSED -gt $TIMEOUT ] && { log_error "Timeout waiting for Knative Service"; exit 1; }

    READY=$(kubectl get ksvc "$KSVC_NAME" -n "$NAMESPACE" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "")

    if [ "$READY" = "True" ]; then
        log_success "Knative Service is Ready"
        break
    fi

    log_info "Waiting for service... ($ELAPSED s)"
    sleep $POLL_INTERVAL
done

# Check worker pod
log_step "3. Checking Worker Pod"
POD=$(kubectl get pods -n "$NAMESPACE" -l "serving.knative.dev/service=$KSVC_NAME" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")

if [ -n "$POD" ]; then
    log_success "Worker pod running: $POD"
    kubectl logs "$POD" -n "$NAMESPACE" -c user-container --tail=20 2>/dev/null || true
else
    log_info "No worker pod found (may have scaled down)"
fi

# Wait for task completion
log_step "4. Waiting for Task Completion"
START=$(date +%s)

while true; do
    ELAPSED=$(($(date +%s) - START))
    [ $ELAPSED -gt $TIMEOUT ] && { log_error "Timeout waiting for task"; exit 1; }

    TASK_RESPONSE=$(curl -s "${API_URL}/v1/agent/tasks/${TASK_ID}")
    STATUS=$(echo "$TASK_RESPONSE" | jq -r '.status // empty')

    case "$STATUS" in
        completed|complete|done)
            log_success "Task completed!"
            break
            ;;
        failed|error)
            log_error "Task failed!"
            echo "$TASK_RESPONSE" | jq .
            exit 1
            ;;
        *)
            log_info "Task status: $STATUS ($ELAPSED s)"
            ;;
    esac

    sleep $POLL_INTERVAL
done

# Verify output
log_step "5. Verifying Task Output"
echo "$TASK_RESPONSE" | jq .

RESULT=$(echo "$TASK_RESPONSE" | jq -r '.result // empty')
ERROR=$(echo "$TASK_RESPONSE" | jq -r '.error // empty')

if [ -n "$ERROR" ] && [ "$ERROR" != "null" ]; then
    log_error "Task has error: $ERROR"
    exit 1
fi

if [ -n "$RESULT" ] && [ "$RESULT" != "null" ]; then
    log_success "Task result: $RESULT"

    # Check if result contains "4"
    if echo "$RESULT" | grep -q "4"; then
        log_success "Result contains expected answer (4)"
    else
        log_error "Result does not contain expected answer"
    fi
else
    log_info "No result field (check task output endpoint)"

    # Try getting output
    OUTPUT=$(curl -s "${API_URL}/v1/agent/tasks/${TASK_ID}/output" | jq -r '.output // empty')
    if [ -n "$OUTPUT" ]; then
        log_info "Task output: $OUTPUT"
    fi
fi

# Summary
log_step "Test Summary"
echo ""
echo "Codebase ID:     $CODEBASE_ID"
echo "Session ID:      $SESSION_ID"
echo "Task ID:         $TASK_ID"
echo "Knative Service: $KSVC_NAME"
echo "Final Status:    $STATUS"
echo ""

if [ "$STATUS" = "completed" ] || [ "$STATUS" = "complete" ] || [ "$STATUS" = "done" ]; then
    echo -e "${GREEN}TEST PASSED${NC}"
    exit 0
else
    echo -e "${RED}TEST FAILED${NC}"
    exit 1
fi
