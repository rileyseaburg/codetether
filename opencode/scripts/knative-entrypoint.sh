#!/bin/sh
set -e

echo "=== OpenCode Knative Worker Starting ==="
echo "Tenant: ${OPENCODE_TENANT_ID:-unset}"
echo "Session: ${OPENCODE_SESSION_ID:-unset}"
echo "Codebase: ${OPENCODE_CODEBASE_ID:-unset}"

# Setup OpenCode config directories (secrets are mounted read-only, need writable copies)
mkdir -p /root/.local/share/opencode
mkdir -p /root/.config/opencode

# Copy auth.json from secret mount if available
if [ -f /secrets/opencode-auth/auth.json ]; then
    cp /secrets/opencode-auth/auth.json /root/.local/share/opencode/auth.json
    echo "Auth config loaded from secret"
fi

# Copy opencode.json from secret mount if available  
if [ -f /secrets/opencode-config/opencode.json ]; then
    cp /secrets/opencode-config/opencode.json /root/.config/opencode/opencode.json
    echo "OpenCode config loaded from secret"
fi

# MinIO client setup using curl (mc not available in alpine by default)
MINIO_PROTOCOL="${MINIO_SECURE:+https}${MINIO_SECURE:-http}"
MINIO_URL="${MINIO_PROTOCOL}://${MINIO_ENDPOINT}"
MINIO_CODEBASE_PATH="${MINIO_BUCKET}/codebases/${OPENCODE_CODEBASE_ID}.tar.gz"

# Function to download codebase from MinIO
download_codebase() {
    if [ -z "${OPENCODE_CODEBASE_ID}" ]; then
        echo "No codebase ID provided, starting with empty workspace"
        mkdir -p /workspace
        return
    fi

    echo "Downloading codebase from MinIO: ${MINIO_CODEBASE_PATH}"
    
    # Check if codebase exists in MinIO
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
        -u "${MINIO_ACCESS_KEY}:${MINIO_SECRET_KEY}" \
        "${MINIO_URL}/${MINIO_CODEBASE_PATH}")
    
    if [ "$STATUS" = "200" ]; then
        curl -s -u "${MINIO_ACCESS_KEY}:${MINIO_SECRET_KEY}" \
            "${MINIO_URL}/${MINIO_CODEBASE_PATH}" | tar -xzf - -C /workspace
        echo "Codebase downloaded and extracted to /workspace"
    else
        echo "No existing codebase found (status: $STATUS), starting fresh"
        mkdir -p /workspace
    fi
}

# Function to sync workspace to MinIO
sync_to_minio() {
    if [ -z "${OPENCODE_CODEBASE_ID}" ]; then
        return
    fi

    echo "Syncing workspace to MinIO..."
    cd /workspace
    tar -czf /tmp/codebase.tar.gz .
    curl -s -X PUT \
        -u "${MINIO_ACCESS_KEY}:${MINIO_SECRET_KEY}" \
        -T /tmp/codebase.tar.gz \
        "${MINIO_URL}/${MINIO_CODEBASE_PATH}"
    rm -f /tmp/codebase.tar.gz
    echo "Sync complete at $(date)"
}

# Function to commit changes to git (if git repo)
git_commit_changes() {
    cd /workspace
    if [ -d ".git" ]; then
        # Configure git if not already
        git config user.email "${GIT_USER_EMAIL:-opencode@codetether.run}" 2>/dev/null || true
        git config user.name "${GIT_USER_NAME:-OpenCode Worker}" 2>/dev/null || true
        
        # Check for changes
        if ! git diff --quiet HEAD 2>/dev/null || [ -n "$(git ls-files --others --exclude-standard)" ]; then
            git add -A
            git commit -m "Auto-commit from OpenCode session ${OPENCODE_SESSION_ID:-unknown}" 2>/dev/null || true
            echo "Git commit created"
        fi
    fi
}

# Background sync loop
background_sync() {
    while true; do
        sleep ${SYNC_INTERVAL_SECONDS:-30}
        git_commit_changes
        sync_to_minio
    done
}

# Download codebase
download_codebase

# Start background sync
background_sync &
SYNC_PID=$!

# Trap to sync on exit
cleanup() {
    echo "Worker shutting down, final sync..."
    kill $SYNC_PID 2>/dev/null || true
    git_commit_changes
    sync_to_minio
    echo "Cleanup complete"
}
trap cleanup EXIT TERM INT

# Change to workspace directory
cd /workspace

# Start OpenCode server
echo "Starting OpenCode server on port ${PORT:-8080}..."
exec bun run --cwd /app/packages/opencode src/index.ts serve \
    --hostname 0.0.0.0 \
    --port ${PORT:-8080} \
    --print-logs
