#!/usr/bin/env bash
set -euo pipefail

# Upsert a Keycloak OIDC client using the Keycloak Admin CLI (kcadm.sh).
#
# Why
# ----
# This repo ships scripts that use OIDC Authorization Code + PKCE (browser session)
# and/or the Resource Owner Password grant (username/password) for local testing.
# Both flows require a Keycloak client with the right toggles and redirect URIs.
#
# Requirements
# ------------
# - Access to `kcadm.sh` (usually inside a Keycloak container/pod)
# - Keycloak admin credentials
#
# Environment variables
# ---------------------
# Required:
#   KEYCLOAK_URL                 e.g. https://auth.example.com
#   KEYCLOAK_REALM               e.g. myrealm
#   KEYCLOAK_CLIENT_ID           e.g. a2a-monitor
#   KEYCLOAK_ADMIN_USERNAME      e.g. admin
#   KEYCLOAK_ADMIN_PASSWORD      e.g. ...
# Optional:
#   KEYCLOAK_ADMIN_REALM         default: master
#   KEYCLOAK_PUBLIC_CLIENT       default: false (confidential client)
#   KEYCLOAK_REDIRECT_URIS       CSV list; default: http://127.0.0.1:8765/*,http://localhost:8765/*
#   KEYCLOAK_WEB_ORIGINS         CSV list; default: http://127.0.0.1:8765,http://localhost:8765
#   KCADM_BIN                    path to kcadm.sh (auto-detected if on PATH)
#   DRY_RUN                      set to 1 to print actions without applying
#
# Notes
# -----
# - If the client is confidential (default), Keycloak will generate a client secret.
#   The script will print it so you can set KEYCLOAK_CLIENT_SECRET.

_die() {
  echo "error: $*" >&2
  exit 1
}

_bool() {
  case "${1,,}" in
    1|true|yes|y|on) echo "true" ;;
    0|false|no|n|off|"") echo "false" ;;
    *) _die "invalid boolean: '$1'" ;;
  esac
}

: "${KEYCLOAK_URL:?KEYCLOAK_URL is required}"
: "${KEYCLOAK_REALM:?KEYCLOAK_REALM is required}"
: "${KEYCLOAK_CLIENT_ID:?KEYCLOAK_CLIENT_ID is required}"
: "${KEYCLOAK_ADMIN_USERNAME:?KEYCLOAK_ADMIN_USERNAME is required}"
: "${KEYCLOAK_ADMIN_PASSWORD:?KEYCLOAK_ADMIN_PASSWORD is required}"

KEYCLOAK_ADMIN_REALM="${KEYCLOAK_ADMIN_REALM:-master}"
KEYCLOAK_PUBLIC_CLIENT="$(_bool "${KEYCLOAK_PUBLIC_CLIENT:-false}")"
KEYCLOAK_REDIRECT_URIS="${KEYCLOAK_REDIRECT_URIS:-http://127.0.0.1:8765/*,http://localhost:8765/*}"
KEYCLOAK_WEB_ORIGINS="${KEYCLOAK_WEB_ORIGINS:-http://127.0.0.1:8765,http://localhost:8765}"
DRY_RUN="$(_bool "${DRY_RUN:-false}")"

KCADM_BIN="${KCADM_BIN:-}"
if [[ -z "$KCADM_BIN" ]]; then
  if command -v kcadm.sh >/dev/null 2>&1; then
    KCADM_BIN="$(command -v kcadm.sh)"
  fi
fi
[[ -n "$KCADM_BIN" ]] || _die "kcadm.sh not found. Set KCADM_BIN or ensure kcadm.sh is on PATH."
[[ -x "$KCADM_BIN" ]] || _die "kcadm.sh is not executable: $KCADM_BIN"

_tmp_json="$(mktemp)"
cleanup() { rm -f "$_tmp_json"; }
trap cleanup EXIT

python3 - <<'PY' >"$_tmp_json"
import json
import os

def csv_to_list(s: str) -> list[str]:
    s = (s or "").strip()
    if not s:
        return []
    return [item.strip() for item in s.split(",") if item.strip()]

client_id = os.environ["KEYCLOAK_CLIENT_ID"]
public_client = os.environ.get("KEYCLOAK_PUBLIC_CLIENT", "false").lower() == "true"
redirect_uris = csv_to_list(os.environ.get("KEYCLOAK_REDIRECT_URIS"))
web_origins = csv_to_list(os.environ.get("KEYCLOAK_WEB_ORIGINS"))

payload = {
    "clientId": client_id,
    "enabled": True,
    "protocol": "openid-connect",

    # Auth code flow (required for browser-based user session tests)
    "standardFlowEnabled": True,

    # Password grant (used by /v1/auth/login)
    "directAccessGrantsEnabled": True,

    # Keep it simple (no implicit flow)
    "implicitFlowEnabled": False,

    # CORS / redirects
    "redirectUris": redirect_uris,
    "webOrigins": web_origins,

    # Public vs confidential client
    "publicClient": public_client,
}

# For confidential clients, ensure client-secret auth type.
if not public_client:
    payload["clientAuthenticatorType"] = "client-secret"

print(json.dumps(payload, indent=2))
PY

if [[ "$DRY_RUN" == "true" ]]; then
  echo "[dry-run] Would configure admin credentials against: $KEYCLOAK_URL (realm: $KEYCLOAK_ADMIN_REALM)"
  echo "[dry-run] Would upsert client '$KEYCLOAK_CLIENT_ID' in realm '$KEYCLOAK_REALM'"
  echo "[dry-run] Client JSON:"; cat "$_tmp_json"
  exit 0
fi

# Login as admin
"$KCADM_BIN" config credentials \
  --server "$KEYCLOAK_URL" \
  --realm "$KEYCLOAK_ADMIN_REALM" \
  --user "$KEYCLOAK_ADMIN_USERNAME" \
  --password "$KEYCLOAK_ADMIN_PASSWORD" \
  >/dev/null

# Resolve client UUID
client_list_json="$("$KCADM_BIN" get clients -r "$KEYCLOAK_REALM" -q "clientId=$KEYCLOAK_CLIENT_ID")"
client_uuid="$(python3 - <<'PY'
import json, sys
arr = json.loads(sys.stdin.read() or "[]")
print(arr[0].get("id", "") if arr else "")
PY
<<<"$client_list_json")"

if [[ -z "$client_uuid" ]]; then
  echo "Creating client '$KEYCLOAK_CLIENT_ID' in realm '$KEYCLOAK_REALM'..." >&2
  "$KCADM_BIN" create clients -r "$KEYCLOAK_REALM" -f "$_tmp_json" >/dev/null

  client_list_json="$("$KCADM_BIN" get clients -r "$KEYCLOAK_REALM" -q "clientId=$KEYCLOAK_CLIENT_ID")"
  client_uuid="$(python3 - <<'PY'
import json, sys
arr = json.loads(sys.stdin.read() or "[]")
print(arr[0].get("id", "") if arr else "")
PY
<<<"$client_list_json")"
  [[ -n "$client_uuid" ]] || _die "client created but could not resolve its id"
else
  echo "Updating client '$KEYCLOAK_CLIENT_ID' ($client_uuid) in realm '$KEYCLOAK_REALM'..." >&2
  "$KCADM_BIN" update "clients/$client_uuid" -r "$KEYCLOAK_REALM" -f "$_tmp_json" >/dev/null
fi

echo "OK: client upserted" >&2

echo "KEYCLOAK_URL=$KEYCLOAK_URL"
echo "KEYCLOAK_REALM=$KEYCLOAK_REALM"
echo "KEYCLOAK_CLIENT_ID=$KEYCLOAK_CLIENT_ID"

if [[ "$KEYCLOAK_PUBLIC_CLIENT" == "false" ]]; then
  # Print the current secret (handy for wiring into .env / helm values)
  secret_json="$("$KCADM_BIN" get "clients/$client_uuid/client-secret" -r "$KEYCLOAK_REALM")"
  client_secret="$(python3 - <<'PY'
import json, sys
obj = json.loads(sys.stdin.read() or "{}")
print(obj.get("value", ""))
PY
<<<"$secret_json")"

  if [[ -n "$client_secret" ]]; then
    echo "KEYCLOAK_CLIENT_SECRET=$client_secret"
  else
    echo "# NOTE: could not fetch client secret (client may be public or Keycloak policy denied it)." >&2
  fi
else
  echo "# Public client: no KEYCLOAK_CLIENT_SECRET needed." >&2
fi

# Remind about local test redirect URIs
echo "# Redirect URIs: $KEYCLOAK_REDIRECT_URIS" >&2
