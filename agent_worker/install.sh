#!/bin/bash
#
# A2A Agent Worker Installation Script
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

# Check root
if [[ $EUID -ne 0 ]]; then
   log_error "This script must be run as root (use sudo)"
   exit 1
fi

# Configuration
INSTALL_DIR="/opt/a2a-worker"
CONFIG_DIR="/etc/a2a-worker"
WORKER_USER="a2a-worker"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REAL_USER="${SUDO_USER:-$USER}"

log_info "Installing A2A Agent Worker..."

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

# Copy worker script
log_info "Installing worker script..."
cp "$SCRIPT_DIR/worker.py" "$INSTALL_DIR/worker.py"
chmod +x "$INSTALL_DIR/worker.py"

# Create virtual environment
log_info "Creating Python virtual environment..."
python3 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install aiohttp

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
EOF
    chmod 600 "$CONFIG_DIR/env"
fi

# Set ownership
log_info "Setting permissions..."
chown -R "$WORKER_USER:$WORKER_USER" "$INSTALL_DIR"
chown -R "$WORKER_USER:$WORKER_USER" "$CONFIG_DIR"

# Install systemd service
log_info "Installing systemd service..."
cp "$SCRIPT_DIR/systemd/a2a-agent-worker.service" /etc/systemd/system/
systemctl daemon-reload

# Enable service
log_info "Enabling service..."
systemctl enable a2a-agent-worker.service

log_info "============================================"
log_info "A2A Agent Worker installed successfully!"
log_info "============================================"
echo ""
log_info "Next steps:"
echo "  1. Edit configuration: sudo nano $CONFIG_DIR/config.json"
echo "  2. Add your codebases to the config"
echo "  3. Start the service: sudo systemctl start a2a-agent-worker"
echo "  4. Check status: sudo systemctl status a2a-agent-worker"
echo "  5. View logs: sudo journalctl -u a2a-agent-worker -f"
echo ""
log_info "Quick start command:"
echo "  sudo systemctl start a2a-agent-worker && sudo journalctl -u a2a-agent-worker -f"
