#!/usr/bin/env bash
set -euo pipefail

# CodeTether user-level installer (no root)
# - Creates a venv under ~/.codetether/venv
# - Installs CodeTether (from PyPI if available, else from GitHub)
# - Symlinks `codetether` and `codetether-worker` into ~/.local/bin

APP=codetether
DEFAULT_PREFIX="$HOME/.codetether"
PREFIX="${CODETETHER_PREFIX:-$DEFAULT_PREFIX}"
VENV_DIR="$PREFIX/venv"
BIN_DIR="$HOME/.local/bin"

log() { printf "[%s] %s\n" "$APP" "$*"; }

need() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "[$APP] Missing required command: $1" >&2
    exit 1
  }
}

need python3
need curl

mkdir -p "$PREFIX"
mkdir -p "$BIN_DIR"

log "Creating virtual environment at: $VENV_DIR"
python3 -m venv "$VENV_DIR"

# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"

log "Upgrading pip"
pip install --upgrade pip >/dev/null

# Try PyPI first; fall back to GitHub source install.
if pip install --upgrade codetether >/dev/null 2>&1; then
  log "Installed CodeTether from PyPI"
else
  # Default to the public GitHub repo. Override with CODETETHER_GIT_URL.
  GIT_URL="${CODETETHER_GIT_URL:-https://github.com/rileyseaburg/codetether.git}"
  # Default branch/ref. Override with CODETETHER_GIT_REF (e.g. main, v1.0.0).
  GIT_REF="${CODETETHER_GIT_REF:-main}"

  log "PyPI install failed; installing from source: $GIT_URL@$GIT_REF"
  pip install --upgrade "git+$GIT_URL@$GIT_REF" >/dev/null
fi

log "Linking CLIs into: $BIN_DIR"
ln -sf "$VENV_DIR/bin/codetether" "$BIN_DIR/codetether"
ln -sf "$VENV_DIR/bin/codetether-worker" "$BIN_DIR/codetether-worker" || true

log "Done. Verify:"
log "  $BIN_DIR/codetether --version"
log "  $BIN_DIR/codetether --help"

if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
  cat >&2 <<EOF
[$APP] NOTE: $BIN_DIR is not on your PATH.
[$APP] Add this to your shell profile (~/.bashrc, ~/.zshrc):

  export PATH="$BIN_DIR:\$PATH"

EOF
fi
