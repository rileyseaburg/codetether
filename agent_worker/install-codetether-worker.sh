#!/bin/bash
#
# CodeTether Worker Installation Script
#
# Installs the codetether Rust binary as a systemd A2A worker service.
# Run as root or with sudo.
#
# Usage:
#   sudo ./install-codetether-worker.sh
#   sudo ./install-codetether-worker.sh --binary /path/to/codetether
#   sudo ./install-codetether-worker.sh --from-cargo   # build from source
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step()  { echo -e "${CYAN}[STEP]${NC} $1"; }

# Check root
if [[ $EUID -ne 0 ]]; then
    log_error "This script must be run as root (use sudo)"
    exit 1
fi

# ─── Parse arguments ────────────────────────────────────────────────
BINARY_PATH=""
FROM_CARGO=0
SERVER_URL=""
CODEBASES=""
AUTO_APPROVE=""

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --binary)       BINARY_PATH="$2"; shift ;;
        --from-cargo)   FROM_CARGO=1 ;;
        --server)       SERVER_URL="$2"; shift ;;
        --codebases)    CODEBASES="$2"; shift ;;
        --auto-approve) AUTO_APPROVE="$2"; shift ;;
        -h|--help)
            echo "Usage: sudo $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --binary PATH       Path to pre-built codetether binary"
            echo "  --from-cargo        Build from source using cargo (requires Rust toolchain)"
            echo "  --server URL        A2A server URL (default: https://api.codetether.run)"
            echo "  --codebases PATHS   Comma-separated codebase paths (e.g. /home/user/project)"
            echo "  --auto-approve MODE Tool approval policy: all, safe, none (default: safe)"
            echo "  -h, --help          Show this help"
            exit 0
            ;;
        *) log_error "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

# ─── Configuration ──────────────────────────────────────────────────
INSTALL_DIR="/opt/codetether-worker"
CONFIG_DIR="/etc/codetether-worker"
WORKER_USER="a2a-worker"
SERVICE_NAME="codetether-worker"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REAL_USER="${SUDO_USER:-$USER}"
DEFAULT_SERVER_URL="${SERVER_URL:-https://api.codetether.run}"
DEFAULT_CODEBASES="${CODEBASES:-/opt/codetether-worker/codebases}"
DEFAULT_AUTO_APPROVE="${AUTO_APPROVE:-safe}"

log_info "Installing CodeTether Worker (Rust binary, SSE-based)..."
echo ""

# ─── Step 1: Create worker user ────────────────────────────────────
log_step "1/7 Creating worker user..."
if ! id "$WORKER_USER" &>/dev/null; then
    useradd --system --shell /bin/false --home-dir "$INSTALL_DIR" "$WORKER_USER"
    log_info "Created system user: $WORKER_USER"
else
    log_info "User $WORKER_USER already exists"
fi

# Add worker user to the real user's group (for codebase access)
if [[ -n "$REAL_USER" ]] && [[ "$REAL_USER" != "root" ]]; then
    usermod -a -G "$REAL_USER" "$WORKER_USER" 2>/dev/null || true
    log_info "Added $WORKER_USER to $REAL_USER's group"
fi

# ─── Step 2: Create directories ────────────────────────────────────
log_step "2/7 Creating directories..."
mkdir -p "$INSTALL_DIR/bin"
mkdir -p "$INSTALL_DIR/.cache"
mkdir -p "$INSTALL_DIR/.config/codetether"
mkdir -p "$CONFIG_DIR"

# ─── Step 3: Install binary ────────────────────────────────────────
log_step "3/7 Installing codetether binary..."

if [[ -n "$BINARY_PATH" ]]; then
    # User provided a binary path
    if [[ ! -f "$BINARY_PATH" ]]; then
        log_error "Binary not found at $BINARY_PATH"
        exit 1
    fi
    cp "$BINARY_PATH" "$INSTALL_DIR/bin/codetether"
    chmod +x "$INSTALL_DIR/bin/codetether"
    log_info "Installed binary from $BINARY_PATH"

elif [[ "$FROM_CARGO" -eq 1 ]]; then
    # Build from source
    AGENT_DIR="$SCRIPT_DIR/../codetether-agent"
    if [[ ! -d "$AGENT_DIR" ]]; then
        log_error "codetether-agent source not found at $AGENT_DIR"
        exit 1
    fi
    log_info "Building codetether from source (this may take a few minutes)..."
    # Build as the real user if possible (cargo doesn't like running as root)
    if [[ -n "$REAL_USER" ]] && [[ "$REAL_USER" != "root" ]]; then
        su -c "cd '$AGENT_DIR' && cargo build --release" "$REAL_USER"
    else
        cd "$AGENT_DIR" && cargo build --release
    fi
    cp "$AGENT_DIR/target/release/codetether" "$INSTALL_DIR/bin/codetether"
    chmod +x "$INSTALL_DIR/bin/codetether"
    log_info "Built and installed codetether binary"

else
    # Auto-detect: check workspace build, then cargo target, then system PATH
    FOUND=0

    # Check workspace release build
    WORKSPACE_BIN="$SCRIPT_DIR/../codetether-agent/target/release/codetether"
    if [[ -f "$WORKSPACE_BIN" ]]; then
        cp "$WORKSPACE_BIN" "$INSTALL_DIR/bin/codetether"
        chmod +x "$INSTALL_DIR/bin/codetether"
        log_info "Installed from workspace build: $WORKSPACE_BIN"
        FOUND=1
    fi

    # Check common cargo install location
    if [[ "$FOUND" -eq 0 ]]; then
        REAL_HOME=""
        if [[ -n "$REAL_USER" ]] && id "$REAL_USER" &>/dev/null; then
            REAL_HOME="$(eval echo "~$REAL_USER" 2>/dev/null || true)"
        fi
        CARGO_BIN="$REAL_HOME/.cargo/bin/codetether"
        if [[ -f "$CARGO_BIN" ]]; then
            cp "$CARGO_BIN" "$INSTALL_DIR/bin/codetether"
            chmod +x "$INSTALL_DIR/bin/codetether"
            log_info "Installed from cargo: $CARGO_BIN"
            FOUND=1
        fi
    fi

    # Check system PATH
    if [[ "$FOUND" -eq 0 ]]; then
        SYS_BIN="$(which codetether 2>/dev/null || true)"
        if [[ -n "$SYS_BIN" ]]; then
            cp "$SYS_BIN" "$INSTALL_DIR/bin/codetether"
            chmod +x "$INSTALL_DIR/bin/codetether"
            log_info "Installed from system PATH: $SYS_BIN"
            FOUND=1
        fi
    fi

    if [[ "$FOUND" -eq 0 ]]; then
        log_error "Could not find codetether binary. Options:"
        echo "  1. Build from source:  sudo $0 --from-cargo"
        echo "  2. Provide binary:     sudo $0 --binary /path/to/codetether"
        echo "  3. Install via cargo:  cargo install --path codetether-agent"
        exit 1
    fi
fi

# Verify the binary works
if "$INSTALL_DIR/bin/codetether" --version &>/dev/null; then
    VERSION=$("$INSTALL_DIR/bin/codetether" --version 2>&1 || echo "unknown")
    log_info "Binary verified: $VERSION"
else
    log_warn "Binary exists but --version check failed. Continuing anyway."
fi

# ─── Step 4: Create environment file ───────────────────────────────
log_step "4/7 Creating configuration..."

if [[ ! -f "$CONFIG_DIR/env" ]]; then
    cat > "$CONFIG_DIR/env" << EOF
# CodeTether Worker Environment
# ---
# This file is loaded by the systemd service unit.
# Uncomment and modify as needed.

# A2A server URL (SSE endpoint for task streaming)
A2A_SERVER_URL=$DEFAULT_SERVER_URL

# Worker identity
A2A_WORKER_NAME=$(hostname)
# A2A_WORKER_ID=  # auto-generated if not set

# Auto-approve policy for tool calls: all, safe (read-only), none
A2A_AUTO_APPROVE=$DEFAULT_AUTO_APPROVE

# Comma-separated paths to codebases this worker owns.
# The server routes tasks to workers based on codebase ownership.
# Example: /home/user/project-a,/home/user/project-b
A2A_CODEBASES=$DEFAULT_CODEBASES

# Log level (trace, debug, info, warn, error)
CODETETHER_LOG_LEVEL=info

# ─── LLM Provider API Keys ─────────────────────────────────
# At least one provider key is required.
# ANTHROPIC_API_KEY=sk-ant-...
# OPENAI_API_KEY=sk-...
# GOOGLE_GENERATIVE_AI_API_KEY=...

# ─── HashiCorp Vault (optional, for centralized secrets) ───
# VAULT_ADDR=https://vault.example.com
# VAULT_TOKEN=hvs...
# VAULT_SECRET_PATH=secret/data/codetether

# ─── Email Notifications (optional) ────────────────────────
# SENDGRID_API_KEY=SG.xxx
# SENDGRID_FROM_EMAIL=noreply@yourdomain.com
# NOTIFICATION_EMAIL=you@example.com

# ─── XDG directories (keep data under service home) ────────
HOME=/opt/codetether-worker
XDG_CACHE_HOME=/opt/codetether-worker/.cache
XDG_CONFIG_HOME=/opt/codetether-worker/.config
EOF
    chmod 600 "$CONFIG_DIR/env"
    log_info "Created $CONFIG_DIR/env"
else
    log_info "Environment file already exists, keeping it"
fi

# ─── Step 5: Set ownership ─────────────────────────────────────────
log_step "5/7 Setting permissions..."
chown -R "$WORKER_USER:$WORKER_USER" "$INSTALL_DIR"

# Config dir: owned by installing user for easy editing
if [[ -n "$REAL_USER" ]] && [[ "$REAL_USER" != "root" ]]; then
    chown -R "$REAL_USER:$REAL_USER" "$CONFIG_DIR"
    chmod 755 "$CONFIG_DIR"
    chmod 600 "$CONFIG_DIR/env" 2>/dev/null || true
else
    chown -R "$WORKER_USER:$WORKER_USER" "$CONFIG_DIR"
fi

# ─── Step 6: Install systemd service ───────────────────────────────
log_step "6/7 Installing systemd service..."

# Use the new service file from this directory
SERVICE_FILE="$SCRIPT_DIR/systemd/codetether-worker.service"
if [[ ! -f "$SERVICE_FILE" ]]; then
    log_error "Service file not found: $SERVICE_FILE"
    exit 1
fi

cp "$SERVICE_FILE" "/etc/systemd/system/$SERVICE_NAME.service"
systemctl daemon-reload
systemctl enable "$SERVICE_NAME.service"
log_info "Systemd service installed and enabled"

# ─── Step 7: Migrate from old worker (if present) ──────────────────
log_step "7/7 Checking for legacy worker..."

OLD_SERVICE="a2a-agent-worker"
if systemctl is-enabled "$OLD_SERVICE" &>/dev/null 2>&1; then
    log_warn "Found legacy $OLD_SERVICE service. Stopping and disabling..."
    systemctl stop "$OLD_SERVICE" 2>/dev/null || true
    systemctl disable "$OLD_SERVICE" 2>/dev/null || true
    log_info "Legacy worker disabled. Old files remain at /opt/a2a-worker for manual cleanup."
fi

# ─── Done ───────────────────────────────────────────────────────────
echo ""
log_info "============================================"
log_info "CodeTether Worker installed successfully!"
log_info "============================================"
echo ""
log_info "Binary:  $INSTALL_DIR/bin/codetether"
log_info "Config:  $CONFIG_DIR/env"
log_info "Service: $SERVICE_NAME"
echo ""
log_info "Next steps:"
echo "  1. Add LLM API key:   sudo nano $CONFIG_DIR/env"
echo "     (set ANTHROPIC_API_KEY, OPENAI_API_KEY, or GOOGLE_GENERATIVE_AI_API_KEY)"
echo ""
echo "  2. Set codebase paths: sudo nano $CONFIG_DIR/env"
echo "     (set A2A_CODEBASES=/path/to/your/project)"
echo ""
echo "  3. Start the service:  sudo systemctl start $SERVICE_NAME"
echo "  4. Check status:       sudo systemctl status $SERVICE_NAME"
echo "  5. View logs:          sudo journalctl -u $SERVICE_NAME -f"
echo ""
log_info "Quick start:"
echo "  sudo systemctl start $SERVICE_NAME && sudo journalctl -u $SERVICE_NAME -f"
echo ""
log_info "To connect to a local dev server:"
echo "  1. Set A2A_SERVER_URL=http://localhost:8000 in $CONFIG_DIR/env"
echo "  2. sudo systemctl restart $SERVICE_NAME"
