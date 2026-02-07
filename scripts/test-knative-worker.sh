#!/bin/bash
#
# Test script for Per-Session Knative OpenCode Workers
#
# This script tests the full flow:
# 1. Use existing codebase
# 2. Use existing session (or resume one)
# 3. Submit a task via the API
# 4. Watch Knative create a worker
# 5. Monitor task completion
# 6. Verify results
# 7. Cleanup
#
# Usage:
#   ./scripts/test-knative-worker.sh [--no-cleanup] [--api-url URL] [--codebase-id ID]
#
# Requirements:
#   - kubectl configured for the cluster
#   - curl, jq installed
#   - API accessible at https://api.codetether.run (or specify --api-url)
#

set -e

# Configuration
API_URL="${API_URL:-https://api.codetether.run}"
NAMESPACE="a2a-server"
CLEANUP=true
TIMEOUT=180  # 3 minutes max wait
POLL_INTERVAL=5
CODEBASE_ID=""
SESSION_ID=""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --no-cleanup)
            CLEANUP=false
            shift
            ;;
        --api-url)
            API_URL="$2"
            shift 2
            ;;
        --namespace)
            NAMESPACE="$2"
            shift 2
            ;;
        --timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        --codebase-id)
            CODEBASE_ID="$2"
            shift 2
            ;;
        --session-id)
            SESSION_ID="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --no-cleanup       Don't delete Knative resources after test"
            echo "  --api-url URL      API URL (default: https://api.codetether.run)"
            echo "  --namespace NS     Kubernetes namespace (default: a2a-server)"
            echo "  --timeout SECONDS  Max wait time (default: 180)"
            echo "  --codebase-id ID   Use specific codebase"
            echo "  --session-id ID    Use specific session"
            echo "  -h, --help         Show this help"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo ""
    echo -e "${CYAN}=== Step $1: $2 ===${NC}"
}

cleanup() {
    if [ "$CLEANUP" = true ]; then
        log_info "Cleaning up test resources..."

        # Delete Knative service if exists (use short session ID for resource name)
        if [ -n "$SESSION_ID" ]; then
            SHORT_SESSION="${SESSION_ID:0:12}"
            kubectl delete ksvc "codetether-session-${SHORT_SESSION}" -n "$NAMESPACE" 2>/dev/null || true
            kubectl delete trigger "trigger-session-${SHORT_SESSION}" -n "$NAMESPACE" 2>/dev/null || true
        fi

        log_success "Cleanup complete"
    else
        log_warning "Skipping cleanup (--no-cleanup specified)"
        if [ -n "$SESSION_ID" ]; then
            SHORT_SESSION="${SESSION_ID:0:12}"
            log_info "Resources to clean manually:"
            echo "  kubectl delete ksvc codetether-session-${SHORT_SESSION} -n $NAMESPACE"
            echo "  kubectl delete trigger trigger-session-${SHORT_SESSION} -n $NAMESPACE"
        fi
    fi
}

# Trap to ensure cleanup on exit
trap cleanup EXIT

# Check prerequisites
log_step 0 "Checking prerequisites"

if ! command -v kubectl &> /dev/null; then
    log_error "kubectl not found"
    exit 1
fi

if ! command -v curl &> /dev/null; then
    log_error "curl not found"
    exit 1
fi

if ! command -v jq &> /dev/null; then
    log_error "jq not found"
    exit 1
fi

log_success "All prerequisites met"

# Check API health
log_info "Checking API health at ${API_URL}..."
HEALTH=$(curl -s "${API_URL}/health" 2>/dev/null || echo '{}')
if echo "$HEALTH" | jq -e '.status == "healthy"' > /dev/null 2>&1; then
    log_success "API is healthy"
else
    log_error "API health check failed: $HEALTH"
    exit 1
fi

# Check Knative broker
log_info "Checking Knative broker..."
BROKER_STATUS=$(kubectl get broker task-broker -n "$NAMESPACE" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "NotFound")
if [ "$BROKER_STATUS" = "True" ]; then
    log_success "Knative broker is ready"
else
    log_warning "Knative broker not ready (status: $BROKER_STATUS)"
    log_info "Continuing anyway - broker may not be required for this test"
fi

# Check KNATIVE_ENABLED in deployment
log_info "Checking Knative is enabled in A2A server..."
KNATIVE_ENABLED=$(kubectl get deploy codetether-a2a-server -n "$NAMESPACE" -o jsonpath='{.spec.template.spec.containers[0].env[?(@.name=="KNATIVE_ENABLED")].value}' 2>/dev/null || echo "")
if [ "$KNATIVE_ENABLED" = "true" ]; then
    log_success "Knative is enabled in A2A server"
else
    log_warning "Knative is not enabled (KNATIVE_ENABLED=$KNATIVE_ENABLED)"
fi

# Step 1: Get or use existing codebase
log_step 1 "Getting codebase"

if [ -z "$CODEBASE_ID" ]; then
    log_info "No codebase ID specified, fetching first available codebase..."
    CODEBASE_RESPONSE=$(curl -s "${API_URL}/v1/agent/codebases" 2>/dev/null)
    CODEBASE_ID=$(echo "$CODEBASE_RESPONSE" | jq -r '.[0].id // empty')

    if [ -z "$CODEBASE_ID" ]; then
        log_error "No codebases found. Please create one first or specify --codebase-id"
        exit 1
    fi
fi

log_success "Using codebase: $CODEBASE_ID"

# Get codebase details
CODEBASE_INFO=$(curl -s "${API_URL}/v1/agent/codebases/${CODEBASE_ID}" 2>/dev/null)
CODEBASE_NAME=$(echo "$CODEBASE_INFO" | jq -r '.name // "unknown"')
CODEBASE_PATH=$(echo "$CODEBASE_INFO" | jq -r '.path // "unknown"')
log_info "Codebase name: $CODEBASE_NAME"
log_info "Codebase path: $CODEBASE_PATH"

# Step 2: Get or use existing session
log_step 2 "Getting session"

if [ -z "$SESSION_ID" ]; then
    log_info "No session ID specified, fetching most recent session..."
    SESSIONS_RESPONSE=$(curl -s "${API_URL}/v1/agent/codebases/${CODEBASE_ID}/sessions" 2>/dev/null)
    SESSION_ID=$(echo "$SESSIONS_RESPONSE" | jq -r '.sessions[0].id // empty')

    if [ -z "$SESSION_ID" ]; then
        log_warning "No existing sessions found"
        log_info "Will use codebase-level task submission"
    else
        log_success "Using session: $SESSION_ID"
        SESSION_TITLE=$(echo "$SESSIONS_RESPONSE" | jq -r '.sessions[0].title // "unknown"')
        log_info "Session title: $SESSION_TITLE"
    fi
else
    log_success "Using specified session: $SESSION_ID"
fi

# Derive the Knative service name
if [ -n "$SESSION_ID" ]; then
    SHORT_SESSION="${SESSION_ID:0:12}"
    KSVC_NAME="codetether-session-${SHORT_SESSION}"
else
    KSVC_NAME="opencode-codebase-${CODEBASE_ID}"
fi

# Step 3: Check initial Knative state
log_step 3 "Checking initial Knative state"

KSVC_EXISTS=$(kubectl get ksvc "$KSVC_NAME" -n "$NAMESPACE" 2>/dev/null && echo "yes" || echo "no")
if [ "$KSVC_EXISTS" = "no" ]; then
    log_success "No Knative service exists yet (expected for new session)"
else
    log_warning "Knative service already exists: $KSVC_NAME"
    kubectl get ksvc "$KSVC_NAME" -n "$NAMESPACE" -o wide 2>/dev/null || true
fi

# Step 4: Trigger agent (this path uses Knative)
log_step 4 "Triggering agent to spawn Knative worker"

# Build the trigger request
# Using the /trigger endpoint which has Knative integration
TRIGGER_JSON=$(cat <<EOF
{
    "prompt": "What is 2+2? Answer with just the number.",
    "agent": "code",
    "model": ""
}
EOF
)

log_info "Trigger request to /v1/agent/codebases/${CODEBASE_ID}/trigger:"
echo "$TRIGGER_JSON" | jq .

TRIGGER_RESPONSE=$(curl -s -X POST "${API_URL}/v1/agent/codebases/${CODEBASE_ID}/trigger" \
    -H "Content-Type: application/json" \
    -d "$TRIGGER_JSON" 2>/dev/null)

log_info "Trigger response:"
echo "$TRIGGER_RESPONSE" | jq .

# Extract task/run info from response
TASK_ID=$(echo "$TRIGGER_RESPONSE" | jq -r '.task_id // .id // .task.id // empty')
RUN_ID=$(echo "$TRIGGER_RESPONSE" | jq -r '.run_id // empty')
TASK_STATUS=$(echo "$TRIGGER_RESPONSE" | jq -r '.status // empty')
KNATIVE_SERVICE=$(echo "$TRIGGER_RESPONSE" | jq -r '.knative_service // empty')

if [ -n "$TASK_ID" ]; then
    log_success "Triggered task: $TASK_ID"
fi

if [ -n "$RUN_ID" ]; then
    log_success "Run ID: $RUN_ID"
fi

if [ -n "$KNATIVE_SERVICE" ] && [ "$KNATIVE_SERVICE" != "null" ]; then
    log_success "Knative service name from response: $KNATIVE_SERVICE"
    KSVC_NAME="$KNATIVE_SERVICE"
fi

# Check for errors
ERROR=$(echo "$TRIGGER_RESPONSE" | jq -r '.error // .detail // empty')
if [ -n "$ERROR" ] && [ "$ERROR" != "null" ]; then
    log_warning "Response error: $ERROR"
fi

# Step 5: Watch for Knative service creation
log_step 5 "Waiting for Knative service"

START_TIME=$(date +%s)
KSVC_FOUND=false

while true; do
    ELAPSED=$(($(date +%s) - START_TIME))
    if [ $ELAPSED -gt $TIMEOUT ]; then
        log_warning "Timeout waiting for Knative service (${TIMEOUT}s)"
        break
    fi

    KSVC_STATUS=$(kubectl get ksvc "$KSVC_NAME" -n "$NAMESPACE" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "NotFound")

    if [ "$KSVC_STATUS" = "True" ]; then
        log_success "Knative service is ready!"
        KSVC_URL=$(kubectl get ksvc "$KSVC_NAME" -n "$NAMESPACE" -o jsonpath='{.status.url}' 2>/dev/null)
        log_info "Knative service URL: $KSVC_URL"
        KSVC_FOUND=true
        break
    elif [ "$KSVC_STATUS" = "NotFound" ]; then
        # Also check for any session-related services
        FOUND_KSVC=$(kubectl get ksvc -n "$NAMESPACE" -o name 2>/dev/null | grep -i "session\|opencode" | head -1 || true)
        if [ -n "$FOUND_KSVC" ]; then
            log_info "Found Knative service: $FOUND_KSVC (${ELAPSED}s)"
        else
            log_info "Waiting for Knative service to be created... (${ELAPSED}s)"
        fi
    else
        log_info "Knative service status: $KSVC_STATUS (${ELAPSED}s)"
    fi

    sleep $POLL_INTERVAL
done

# Step 6: Check all Knative resources
log_step 6 "Checking Knative resources"

echo ""
echo "All Knative Services:"
kubectl get ksvc -n "$NAMESPACE" 2>/dev/null || echo "  (none found)"

echo ""
echo "All Knative Triggers:"
kubectl get trigger -n "$NAMESPACE" 2>/dev/null || echo "  (none found)"

echo ""
echo "OpenCode Worker Pods:"
kubectl get pods -n "$NAMESPACE" -l "app.kubernetes.io/component=codetether-worker" 2>/dev/null || \
kubectl get pods -n "$NAMESPACE" | grep -E "opencode|session" || echo "  (none found)"

# Step 7: Check task status
log_step 7 "Checking task status"

if [ -n "$TASK_ID" ]; then
    log_info "Polling task status..."

    for i in {1..10}; do
        TASK_STATUS_RESPONSE=$(curl -s "${API_URL}/v1/agent/tasks/${TASK_ID}" 2>/dev/null)
        TASK_STATUS=$(echo "$TASK_STATUS_RESPONSE" | jq -r '.status // empty')

        if [ -n "$TASK_STATUS" ]; then
            log_info "Task status: $TASK_STATUS"

            case "$TASK_STATUS" in
                "completed"|"complete"|"done")
                    log_success "Task completed!"
                    echo "$TASK_STATUS_RESPONSE" | jq .
                    break
                    ;;
                "failed"|"error")
                    log_error "Task failed!"
                    echo "$TASK_STATUS_RESPONSE" | jq .
                    break
                    ;;
            esac
        fi

        sleep 3
    done
else
    log_warning "No task ID to poll"
fi

# Step 8: Check A2A server logs
log_step 8 "Checking A2A server logs for Knative activity"

log_info "Last 30 log lines mentioning 'knative', 'session', or 'worker':"
kubectl logs deploy/codetether-a2a-server -n "$NAMESPACE" --tail=300 2>/dev/null | \
    grep -iE "knative|spawn|worker|session.*creat" | tail -30 || echo "  (no relevant logs found)"

# Step 9: Summary
echo ""
echo "======================================"
echo -e "${CYAN}TEST SUMMARY${NC}"
echo "======================================"
echo ""
echo "Configuration:"
echo "  API URL:        $API_URL"
echo "  Namespace:      $NAMESPACE"
echo "  Knative Enabled: ${KNATIVE_ENABLED:-unknown}"
echo ""
echo "Resources:"
echo "  Codebase ID:    $CODEBASE_ID"
echo "  Codebase Name:  $CODEBASE_NAME"
echo "  Session ID:     ${SESSION_ID:-N/A}"
echo "  Task ID:        ${TASK_ID:-N/A}"
echo ""
echo "Knative:"
echo "  Expected Service: $KSVC_NAME"
echo "  Service Found:    ${KSVC_FOUND}"
echo "  Service URL:      ${KSVC_URL:-Not created}"
echo ""

if [ "$KSVC_FOUND" = true ]; then
    echo -e "${GREEN}Knative worker was successfully created!${NC}"
else
    echo -e "${YELLOW}Knative worker was NOT created.${NC}"
    echo ""
    echo "This could mean:"
    echo "  1. Knative spawning is not yet implemented in the task handler"
    echo "  2. The task was processed by an existing worker"
    echo "  3. There was an error in the spawning logic"
    echo ""
    echo "Check the A2A server logs for more details:"
    echo "  kubectl logs deploy/codetether-a2a-server -n $NAMESPACE --tail=100"
fi

echo ""
exit 0
