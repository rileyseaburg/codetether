#!/bin/bash
#
# CodeTether Agent Worker Installation Script
#
# This script installs the A2A agent worker as a systemd service.
# Run as root or with sudo.
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

ensure_dir() {
    local dir="$1"
    mkdir -p "$dir"
}

ensure_env_kv() {
    local file="$1"
    local key="$2"
    local value="$3"

    # If the key is already set (even if commented elsewhere), don't overwrite.
    if [[ -f "$file" ]] && grep -qE "^${key}=" "$file"; then
        return 0
    fi

    echo "${key}=${value}" >> "$file"
}

# Check root
if [[ $EUID -ne 0 ]]; then
   log_error "This script must be run as root (use sudo)"
   exit 1
fi

# Parse arguments
LOCAL_OPENCODE_PATH=""
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --local-codetether) LOCAL_OPENCODE_PATH="$2"; shift ;;
        *) echo "Unknown parameter passed: $1"; exit 1 ;;
    esac
    shift
done

# Configuration
INSTALL_DIR="/opt/a2a-worker"
CONFIG_DIR="/etc/a2a-worker"
WORKER_USER="a2a-worker"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REAL_USER="${SUDO_USER:-$USER}"

log_info "Installing CodeTether Agent Worker..."

# Create worker user if it doesn't exist
if ! id "$WORKER_USER" &>/dev/null; then
    log_info "Creating user: $WORKER_USER"
    useradd --system --shell /bin/false --home-dir "$INSTALL_DIR" "$WORKER_USER"
else
    log_info "User $WORKER_USER already exists"
fi

# Add worker user to the real user's group (to access codebases)
if [[ -n "$REAL_USER" ]] && [[ "$REAL_USER" != "root" ]]; then
    log_info "Adding $WORKER_USER to $REAL_USER's group for codebase access"
    usermod -a -G "$REAL_USER" "$WORKER_USER"
fi

# Create directories
log_info "Creating directories..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$CONFIG_DIR"
mkdir -p "$INSTALL_DIR/.cache"
ensure_dir "$INSTALL_DIR/.local/share/codetether"
ensure_dir "$INSTALL_DIR/.config/codetether"
ensure_dir "$INSTALL_DIR/.local/state/codetether"

# Install local CodeTether binary if provided
if [[ -n "$LOCAL_OPENCODE_PATH" ]]; then
    log_info "Installing local CodeTether binary from $LOCAL_OPENCODE_PATH..."
    if [[ -f "$LOCAL_OPENCODE_PATH" ]]; then
        # Install to the path expected by config.json
        ensure_dir "$INSTALL_DIR/bin"
        cp "$LOCAL_OPENCODE_PATH" "$INSTALL_DIR/bin/codetether"
        chmod +x "$INSTALL_DIR/bin/codetether"
        chown -R "$WORKER_USER:$WORKER_USER" "$INSTALL_DIR/bin"
        log_info "Local CodeTether binary installed to $INSTALL_DIR/bin/codetether"
    else
        log_error "Local CodeTether binary not found at $LOCAL_OPENCODE_PATH"
        exit 1
    fi
else
    # Auto-detect local codetether build from workspace
    WORKSPACE_OPENCODE="$SCRIPT_DIR/../codetether/packages/codetether/dist"

    # Detect architecture
    arch=$(uname -m)
    [[ "$arch" == "x86_64" ]] && arch="x64"
    [[ "$arch" == "aarch64" ]] && arch="arm64"

    os=$(uname -s | tr '[:upper:]' '[:lower:]')
    [[ "$os" == "darwin" ]] && os="darwin" || os="linux"

    LOCAL_BUILD="$WORKSPACE_OPENCODE/codetether-$os-$arch/bin/codetether"

    if [[ -f "$LOCAL_BUILD" ]]; then
        log_info "Found local CodeTether build at $LOCAL_BUILD"
        ensure_dir "$INSTALL_DIR/bin"
        cp "$LOCAL_BUILD" "$INSTALL_DIR/bin/codetether"
        chmod +x "$INSTALL_DIR/bin/codetether"
        chown -R "$WORKER_USER:$WORKER_USER" "$INSTALL_DIR/bin"
        log_info "Local CodeTether binary installed to $INSTALL_DIR/bin/codetether"
    else
        log_warn "No local CodeTether build found. You may need to install it manually or run:"
        log_warn "  cd codetether/packages/codetether && bun run build --single"
        log_warn "  sudo $0 --local-codetether <path-to-binary>"
    fi
fi

# Copy worker script
log_info "Installing worker script..."
cp "$SCRIPT_DIR/worker.py" "$INSTALL_DIR/worker.py"
chmod +x "$INSTALL_DIR/worker.py"

# Create virtual environment
log_info "Creating Python virtual environment..."
python3 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install aiohttp redis

# Install config file if not exists
if [[ ! -f "$CONFIG_DIR/config.json" ]]; then
    log_info "Installing default configuration..."
    cp "$SCRIPT_DIR/config.example.json" "$CONFIG_DIR/config.json"
    chmod 600 "$CONFIG_DIR/config.json"
    log_warn "Edit $CONFIG_DIR/config.json to configure your codebases"
else
    log_info "Configuration file already exists, keeping it"
fi

# Create environment file
if [[ ! -f "$CONFIG_DIR/env" ]]; then
    log_info "Creating environment file..."
    cat > "$CONFIG_DIR/env" << 'EOF'
# A2A Agent Worker Environment
# Uncomment and modify as needed

# A2A_SERVER_URL=https://api.codetether.run
# A2A_WORKER_NAME=my-worker
# A2A_POLL_INTERVAL=5

# CodeTether writes cache data; keep it in a service-owned path (avoids EACCES on /home/<user>/.cache)
XDG_CACHE_HOME=/opt/a2a-worker/.cache

# Keep CodeTether config/data/state under the service-owned home.
# This lets the systemd worker use imported CodeTether auth (auth.json) without relying on env API keys.
HOME=/opt/a2a-worker
XDG_DATA_HOME=/opt/a2a-worker/.local/share
XDG_CONFIG_HOME=/opt/a2a-worker/.config
XDG_STATE_HOME=/opt/a2a-worker/.local/state

# LLM credentials (required for CodeTether agents). Provide via environment variables.
# The default example CodeTether config often uses Anthropic (including Azure AI Foundry Anthropic endpoints).
# ANTHROPIC_API_KEY=your_key_here

# Email notifications (optional) - get SendGrid API key from https://app.sendgrid.com
# SENDGRID_API_KEY=SG.xxx
# SENDGRID_FROM_EMAIL=noreply@yourdomain.com
# NOTIFICATION_EMAIL=you@example.com

# Email reply configuration - allows users to reply to task emails to continue conversations
# Requires SendGrid Inbound Parse configured to forward to your server's /v1/email/inbound
EMAIL_INBOUND_DOMAIN=inbound.codetether.run
EMAIL_REPLY_PREFIX=task
EOF
    chmod 600 "$CONFIG_DIR/env"
fi

# Ensure required environment defaults exist even if the env file already existed.
ensure_env_kv "$CONFIG_DIR/env" "HOME" "$INSTALL_DIR"
ensure_env_kv "$CONFIG_DIR/env" "XDG_CACHE_HOME" "$INSTALL_DIR/.cache"
ensure_env_kv "$CONFIG_DIR/env" "XDG_DATA_HOME" "$INSTALL_DIR/.local/share"
ensure_env_kv "$CONFIG_DIR/env" "XDG_CONFIG_HOME" "$INSTALL_DIR/.config"
ensure_env_kv "$CONFIG_DIR/env" "XDG_STATE_HOME" "$INSTALL_DIR/.local/state"

# Best-effort import of the invoking user's CodeTether auth/config so the worker can run
# without requiring API keys to be injected into the systemd environment.
REAL_HOME=""
if [[ -n "$REAL_USER" ]] && id "$REAL_USER" &>/dev/null; then
    REAL_HOME="$(eval echo "~$REAL_USER" 2>/dev/null || true)"
fi

if [[ -n "$REAL_HOME" ]] && [[ -d "$REAL_HOME" ]]; then
    SRC_AUTH="$REAL_HOME/.local/share/codetether/auth.json"
    DST_AUTH="$INSTALL_DIR/.local/share/codetether/auth.json"
    if [[ -f "$SRC_AUTH" ]]; then
        if [[ -f "$DST_AUTH" ]] && [[ -z "${A2A_OVERWRITE_OPENCODE_AUTH:-}" ]]; then
            log_info "CodeTether auth already exists for worker (leaving as-is): $DST_AUTH"
            log_info "To overwrite from $SRC_AUTH, re-run with: A2A_OVERWRITE_OPENCODE_AUTH=1"
        else
            log_info "Importing CodeTether auth for worker (auth.json)"
            cp "$SRC_AUTH" "$DST_AUTH"
            chmod 600 "$DST_AUTH"
        fi
    else
        log_warn "No CodeTether auth.json found at $SRC_AUTH (skipping import)"
        log_warn "If CodeTether prompts for an API key, authenticate as '$WORKER_USER' or copy auth.json into $INSTALL_DIR/.local/share/codetether/"
    fi

    SRC_CONFIG="$REAL_HOME/.config/codetether/codetether.json"
    DST_CONFIG="$INSTALL_DIR/.config/codetether/codetether.json"
    if [[ -f "$SRC_CONFIG" ]]; then
        if [[ -f "$DST_CONFIG" ]] && [[ -z "${A2A_OVERWRITE_OPENCODE_CONFIG:-}" ]]; then
            log_info "CodeTether config already exists for worker (leaving as-is): $DST_CONFIG"
            log_info "To overwrite from $SRC_CONFIG, re-run with: A2A_OVERWRITE_OPENCODE_CONFIG=1"
        else
            log_info "Importing CodeTether config for worker (codetether.json)"
            cp "$SRC_CONFIG" "$DST_CONFIG"
            chmod 600 "$DST_CONFIG" || true
        fi
    else
        log_warn "No CodeTether codetether.json found at $SRC_CONFIG (skipping import)"
    fi
else
    log_warn "Could not determine home directory for REAL_USER='$REAL_USER' (skipping CodeTether auth/config import)"
fi

# Set ownership
log_info "Setting permissions..."
chown -R "$WORKER_USER:$WORKER_USER" "$INSTALL_DIR"

# Config directory: owned by installing user for easy editing, readable by worker
if [[ -n "$REAL_USER" ]] && [[ "$REAL_USER" != "root" ]]; then
    log_info "Setting config ownership to $REAL_USER (editable without sudo)"
    chown -R "$REAL_USER:$REAL_USER" "$CONFIG_DIR"
    chmod 755 "$CONFIG_DIR"
    chmod 644 "$CONFIG_DIR/config.json" 2>/dev/null || true
    chmod 644 "$CONFIG_DIR/env" 2>/dev/null || true
else
    chown -R "$WORKER_USER:$WORKER_USER" "$CONFIG_DIR"
fi

# Install systemd service
log_info "Installing systemd service..."
cp "$SCRIPT_DIR/systemd/a2a-agent-worker.service" /etc/systemd/system/
systemctl daemon-reload

# Enable service
log_info "Enabling service..."
systemctl enable a2a-agent-worker.service

log_info "============================================"
log_info "CodeTether Agent Worker installed successfully!"
log_info "============================================"
echo ""
log_info "Configuration files (editable without sudo):"
echo "  - $CONFIG_DIR/config.json  # Worker settings and codebases"
echo "  - $CONFIG_DIR/env          # Environment variables (server URL, API keys)"
echo ""
log_info "Key configuration options:"
echo "  config.json:"
echo "    server_url: API server URL (default: https://api.codetether.run)"
echo "    codebases:  List of codebases to register with the server"
echo ""
echo "  env file:"
echo "    A2A_SERVER_URL: Overrides server_url from config.json"
echo "    A2A_WORKER_NAME: Custom worker name"
echo "    A2A_WORKER_ID: Persistent worker ID (auto-generated if not set)"
echo ""
log_info "Next steps:"
echo "  1. Edit configuration: nano $CONFIG_DIR/config.json"
echo "  2. Set server URL in env: nano $CONFIG_DIR/env"
echo "  3. Start the service: sudo systemctl start a2a-agent-worker"
echo "  4. Check status: sudo systemctl status a2a-agent-worker"
echo "  5. View logs: sudo journalctl -u a2a-agent-worker -f"
echo ""
log_info "Quick start command:"
echo "  sudo systemctl start a2a-agent-worker && sudo journalctl -u a2a-agent-worker -f"
echo ""
log_info "To connect to a local development server:"
echo "  1. Set A2A_SERVER_URL=http://localhost:8000 in $CONFIG_DIR/env"
echo "  2. sudo systemctl restart a2a-agent-worker"
