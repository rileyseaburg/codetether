#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST="${CODETETHER_HOST:-127.0.0.1}"
PORT="${CODETETHER_PORT:-4096}"
TOKEN="${CODETETHER_AUTH_TOKEN:-codetether-local-dev}"
export CODETETHER_AUTH_TOKEN="$TOKEN"

if [[ -x "$ROOT_DIR/codetether-agent/target/release/codetether" ]]; then
  CODETETHER_BIN="$ROOT_DIR/codetether-agent/target/release/codetether"
elif command -v codetether >/dev/null 2>&1; then
  CODETETHER_BIN="$(command -v codetether)"
else
  echo "codetether binary not found" >&2
  exit 1
fi

printf 'MCP URL: http://%s:%s/mcp?token=%s\n' "$HOST" "$PORT" "$TOKEN"
exec "$CODETETHER_BIN" serve --hostname "$HOST" --port "$PORT"