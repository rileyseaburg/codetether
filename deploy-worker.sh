#!/bin/bash
#
# deploy-worker.sh — One-command Rust worker deployment
#
# Deploys the CodeTether Rust worker as a systemd service
# and registers it to one or more codebases.
#
# Usage:
#   ./deploy-worker.sh                                # local dev defaults
#   ./deploy-worker.sh --codebases /home/me/project   # register to a codebase
#   ./deploy-worker.sh --server https://api.codetether.run --codebases /srv/app
#   ./deploy-worker.sh --foreground                   # run in terminal (no systemd)
#
set -e

# ─── Colors ─────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

log()  { echo -e "${GREEN}▸${NC} $1"; }
warn() { echo -e "${YELLOW}▸${NC} $1"; }
err()  { echo -e "${RED}✗${NC} $1" >&2; }
head() { echo -e "\n${BOLD}${CYAN}$1${NC}"; }

# ─── Defaults ───────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_URL="${A2A_SERVER_URL:-http://192.168.50.101:8001}"
WORKER_NAME="${A2A_WORKER_NAME:-$(hostname)}"
CODEBASES="${A2A_CODEBASES:-$SCRIPT_DIR}"
AUTO_APPROVE="safe"
FOREGROUND=0
SYSTEMD=0
BUILD=0

# ─── Parse args ─────────────────────────────────────────────────────
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --server)       SERVER_URL="$2"; shift ;;
        --name)         WORKER_NAME="$2"; shift ;;
        --codebases)    CODEBASES="$2"; shift ;;
        --auto-approve) AUTO_APPROVE="$2"; shift ;;
        --foreground)   FOREGROUND=1 ;;
        --systemd)      SYSTEMD=1 ;;
        --build)        BUILD=1 ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Deploy the CodeTether Rust worker and register it to codebases."
            echo ""
            echo "Options:"
            echo "  --server URL        A2A server URL (default: \$A2A_SERVER_URL or http://192.168.50.101:8001)"
            echo "  --name NAME         Worker name (default: hostname)"
            echo "  --codebases PATHS   Comma-separated codebase paths (default: this repo)"
            echo "  --auto-approve MODE Tool approval: all, safe, none (default: safe)"
            echo "  --foreground        Run in foreground (no systemd, ctrl-c to stop)"
            echo "  --systemd           Install and start as systemd service (requires sudo)"
            echo "  --build             Rebuild the binary before deploying"
            echo ""
            echo "If neither --foreground nor --systemd is given, defaults to --foreground."
            echo ""
            echo "Examples:"
            echo "  $0 --codebases /home/riley/my-project"
            echo "  $0 --codebases /srv/app-a,/srv/app-b --auto-approve all --systemd"
            echo "  $0 --server https://api.codetether.run --systemd"
            exit 0
            ;;
        *) err "Unknown argument: $1"; exit 1 ;;
    esac
    shift
done

# Default to foreground if neither mode specified
if [[ "$FOREGROUND" -eq 0 ]] && [[ "$SYSTEMD" -eq 0 ]]; then
    FOREGROUND=1
fi

# ─── Locate / build binary ─────────────────────────────────────────
BINARY="$SCRIPT_DIR/codetether-agent/target/release/codetether"

if [[ "$BUILD" -eq 1 ]]; then
    head "Building codetether binary..."
    (cd "$SCRIPT_DIR/codetether-agent" && cargo build --release)
    log "Build complete"
fi

if [[ ! -x "$BINARY" ]]; then
    # Try debug build
    BINARY="$SCRIPT_DIR/codetether-agent/target/debug/codetether"
fi

if [[ ! -x "$BINARY" ]]; then
    # Try system PATH
    BINARY="$(which codetether 2>/dev/null || true)"
fi

if [[ -z "$BINARY" ]] || [[ ! -x "$BINARY" ]]; then
    err "codetether binary not found. Build it first:"
    echo "  cd codetether-agent && cargo build --release"
    echo "  Or: $0 --build"
    exit 1
fi

VERSION=$("$BINARY" --version 2>&1 || echo "unknown")

# ─── Summary ────────────────────────────────────────────────────────
head "CodeTether Worker Deployment"
echo ""
log "Binary:       $BINARY ($VERSION)"
log "Server:       $SERVER_URL"
log "Worker name:  $WORKER_NAME"
log "Codebases:    $CODEBASES"
log "Auto-approve: $AUTO_APPROVE"
if [[ "$FOREGROUND" -eq 1 ]]; then
    log "Mode:         foreground (ctrl-c to stop)"
else
    log "Mode:         systemd service"
fi
echo ""

# ─── Validate codebases exist ──────────────────────────────────────
IFS=',' read -ra CB_PATHS <<< "$CODEBASES"
for cb in "${CB_PATHS[@]}"; do
    cb="$(echo "$cb" | xargs)"  # trim whitespace
    if [[ ! -d "$cb" ]]; then
        warn "Codebase path does not exist: $cb"
    else
        log "Codebase verified: $cb"
    fi
done

# ─── Deploy ─────────────────────────────────────────────────────────
if [[ "$FOREGROUND" -eq 1 ]]; then
    head "Starting worker in foreground..."
    echo "Press Ctrl-C to stop"
    echo ""
    exec "$BINARY" worker \
        --server "$SERVER_URL" \
        --name "$WORKER_NAME" \
        --codebases "$CODEBASES" \
        --auto-approve "$AUTO_APPROVE"
else
    head "Installing as systemd service..."
    if [[ $EUID -ne 0 ]]; then
        err "Systemd mode requires root. Re-run with sudo:"
        echo "  sudo $0 --systemd --codebases $CODEBASES"
        exit 1
    fi

    # Run the full install script with our args
    "$SCRIPT_DIR/agent_worker/install-codetether-worker.sh" \
        --binary "$BINARY" \
        --server "$SERVER_URL" \
        --codebases "$CODEBASES" \
        --auto-approve "$AUTO_APPROVE"

    # Start the service
    systemctl start codetether-worker
    echo ""
    head "Worker deployed!"
    log "Check status:  sudo systemctl status codetether-worker"
    log "View logs:     sudo journalctl -u codetether-worker -f"
    log "Stop:          sudo systemctl stop codetether-worker"
fi
