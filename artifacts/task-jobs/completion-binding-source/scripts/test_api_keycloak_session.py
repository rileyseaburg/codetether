#!/usr/bin/env python3
"""Test CodeTether/A2A API using a *user* Keycloak session.

What this does
--------------
1) Starts a small localhost HTTP server to receive the OIDC redirect.
2) Opens a browser to Keycloak (Authorization Code + PKCE).
   - If you're already logged into Keycloak in that browser, this reuses your session.
3) Exchanges the returned authorization code for an access token.
4) Calls the A2A API with `Authorization: Bearer <access_token>`.

Why this exists
---------------
Most A2A endpoints expect a Bearer JWT validated against Keycloak JWKS.
This script lets you test those endpoints *as a user* without embedding a password.

Environment variables (optional)
-------------------------------
- A2A_API_BASE_URL           (default: http://localhost:8000)
- KEYCLOAK_URL               (default: https://auth.quantum-forge.io)
- KEYCLOAK_REALM             (default: quantum-forge)
- KEYCLOAK_CLIENT_ID         (default: a2a-monitor)
- KEYCLOAK_CLIENT_SECRET     (optional; required only for confidential clients)
- KEYCLOAK_REDIRECT_URI      (default: http://127.0.0.1:8765/callback)

Tip: The repo already contains a `.env.example` with these keys.

Examples
--------
# Interactive login (or reuse existing browser session)
# python scripts/test_api_keycloak_session.py

# Reuse an existing Keycloak session *silently* (fails if you are not already logged in)
# python scripts/test_api_keycloak_session.py --prompt none

# Test a different API base URL
# python scripts/test_api_keycloak_session.py --api-base-url https://api.codetether.run

# Use a token you already have (e.g., copied from a client) and skip the browser flow
# KEYCLOAK_ACCESS_TOKEN=... python scripts/test_api_keycloak_session.py
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import secrets
import threading
import time
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlencode, urlparse

import httpx


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _pkce_pair() -> tuple[str, str]:
    # RFC 7636: verifier length 43-128 chars
    verifier = _b64url(secrets.token_bytes(32))
    challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    return verifier, challenge


@dataclass
class OIDCConfig:
    keycloak_url: str
    realm: str
    client_id: str
    client_secret: Optional[str]
    redirect_uri: str

    @property
    def auth_url(self) -> str:
        return f"{self.keycloak_url}/realms/{self.realm}/protocol/openid-connect/auth"

    @property
    def token_url(self) -> str:
        return f"{self.keycloak_url}/realms/{self.realm}/protocol/openid-connect/token"


class _CallbackHandler(BaseHTTPRequestHandler):
    # Set by server owner
    result: Dict[str, Any] = {}

    def log_message(self, format: str, *args: Any) -> None:
        # Silence default HTTPServer logging (keeps output readable)
        return

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)

        self.__class__.result["path"] = parsed.path
        self.__class__.result["query"] = {k: v[0] if v else "" for k, v in qs.items()}

        # Provide a friendly page in the browser
        html = (
            "<html><body style='font-family: ui-sans-serif, system-ui; padding: 24px;'>"
            "<h2>✅ Login received</h2>"
            "<p>You can close this tab and return to your terminal.</p>"
            "</body></html>"
        ).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html)))
        self.end_headers()
        self.wfile.write(html)


def _start_callback_server(redirect_uri: str) -> tuple[HTTPServer, threading.Thread, str]:
    parsed = urlparse(redirect_uri)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"redirect_uri must be http/https, got: {redirect_uri}")
    if not parsed.hostname or not parsed.port:
        raise ValueError(
            "redirect_uri must include hostname and port, e.g. http://127.0.0.1:8765/callback"
        )

    host = parsed.hostname
    port = parsed.port
    expected_path = parsed.path or "/"

    _CallbackHandler.result = {}
    server = HTTPServer((host, port), _CallbackHandler)

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    return server, thread, expected_path


def _wait_for_auth_code(expected_path: str, timeout_s: int) -> Dict[str, str]:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        r = _CallbackHandler.result.get("query")
        path = _CallbackHandler.result.get("path")
        if r and path == expected_path:
            return r
        time.sleep(0.05)
    raise TimeoutError(
        "Timed out waiting for browser redirect. "
        "If you ran with --no-browser, open the printed URL and complete login."
    )


def _exchange_code_for_token(
    http: httpx.Client,
    cfg: OIDCConfig,
    code: str,
    code_verifier: str,
) -> Dict[str, Any]:
    data = {
        "grant_type": "authorization_code",
        "client_id": cfg.client_id,
        "code": code,
        "redirect_uri": cfg.redirect_uri,
        "code_verifier": code_verifier,
    }
    if cfg.client_secret:
        data["client_secret"] = cfg.client_secret

    resp = http.post(cfg.token_url, data=data)
    resp.raise_for_status()
    return resp.json()


def _call_api(http: httpx.Client, api_base_url: str, token: str) -> None:
    api_base_url = api_base_url.rstrip("/")

    # Basic sanity check: server health
    health = http.get(f"{api_base_url}/health")
    print(f"GET /health -> {health.status_code}")

    # Auth sanity check: who am I?
    me = http.get(
        f"{api_base_url}/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    print(f"GET /v1/auth/me -> {me.status_code}")
    try:
        me_json = me.json()
        print(json.dumps(me_json, indent=2))
    except Exception:
        print(me.text)
        me_json = {}

    # If we got a userId back, also try a user-scoped endpoint.
    user_id = me_json.get("userId")
    if user_id:
        codebases = http.get(
            f"{api_base_url}/v1/auth/user/{user_id}/codebases",
            headers={"Authorization": f"Bearer {token}"},
        )
        print(f"GET /v1/auth/user/{{userId}}/codebases -> {codebases.status_code}")
        try:
            print(json.dumps(codebases.json(), indent=2))
        except Exception:
            print(codebases.text)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Test A2A API endpoints using a Keycloak user session (OIDC auth code + PKCE)."
    )

    parser.add_argument(
        "--api-base-url",
        default=os.environ.get("A2A_API_BASE_URL", "http://localhost:8000"),
        help="A2A server base URL (default: %(default)s)",
    )

    parser.add_argument(
        "--keycloak-url",
        default=os.environ.get("KEYCLOAK_URL", "https://auth.quantum-forge.io"),
        help="Keycloak base URL (default: %(default)s)",
    )
    parser.add_argument(
        "--realm",
        default=os.environ.get("KEYCLOAK_REALM", "quantum-forge"),
        help="Keycloak realm (default: %(default)s)",
    )
    parser.add_argument(
        "--client-id",
        default=os.environ.get("KEYCLOAK_CLIENT_ID", "a2a-monitor"),
        help="OIDC client id (default: %(default)s)",
    )
    parser.add_argument(
        "--client-secret",
        default=os.environ.get("KEYCLOAK_CLIENT_SECRET"),
        help="OIDC client secret (only for confidential clients; optional)",
    )

    parser.add_argument(
        "--redirect-uri",
        default=os.environ.get("KEYCLOAK_REDIRECT_URI", "http://127.0.0.1:8765/callback"),
        help="Redirect URI registered in Keycloak (default: %(default)s)",
    )

    parser.add_argument(
        "--prompt",
        choices=["login", "none"],
        default="login",
        help="OIDC prompt parameter. Use 'none' to reuse an existing browser session without re-prompting (default: %(default)s)",
    )

    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open a browser automatically (prints the login URL)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=180,
        help="Seconds to wait for redirect (default: %(default)s)",
    )

    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable TLS verification (use only for local/dev)",
    )

    args = parser.parse_args()

    # If user already has a token (e.g. copied from a client session), use it directly.
    existing_token = os.environ.get("KEYCLOAK_ACCESS_TOKEN") or os.environ.get("A2A_ACCESS_TOKEN")
    if existing_token:
        print("Using access token from env (KEYCLOAK_ACCESS_TOKEN/A2A_ACCESS_TOKEN).")
        with httpx.Client(verify=not args.insecure, timeout=30.0, follow_redirects=True) as http:
            _call_api(http, args.api_base_url, existing_token)
        return 0

    cfg = OIDCConfig(
        keycloak_url=args.keycloak_url.rstrip("/"),
        realm=args.realm,
        client_id=args.client_id,
        client_secret=args.client_secret,
        redirect_uri=args.redirect_uri,
    )

    code_verifier, code_challenge = _pkce_pair()
    state = _b64url(secrets.token_bytes(16))

    params = {
        "client_id": cfg.client_id,
        "response_type": "code",
        "scope": "openid profile email",
        "redirect_uri": cfg.redirect_uri,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "prompt": args.prompt,
    }

    login_url = f"{cfg.auth_url}?{urlencode(params)}"

    server, _thread, expected_path = _start_callback_server(cfg.redirect_uri)

    try:
        print("\nOpen this URL to authenticate (or reuse your existing Keycloak browser session):\n")
        print(login_url)
        print("")

        if not args.no_browser:
            try:
                webbrowser.open(login_url, new=2)
            except Exception:
                # If opening a browser fails (headless), user can still copy/paste.
                pass

        qs = _wait_for_auth_code(expected_path=expected_path, timeout_s=args.timeout)

        if qs.get("state") != state:
            raise RuntimeError("State mismatch in callback (possible CSRF / wrong redirect).")

        if "error" in qs:
            raise RuntimeError(f"OIDC error: {qs.get('error')} ({qs.get('error_description', '')})")

        code = qs.get("code")
        if not code:
            raise RuntimeError("No authorization code received in callback.")

        with httpx.Client(verify=not args.insecure, timeout=30.0, follow_redirects=True) as http:
            token_data = _exchange_code_for_token(http=http, cfg=cfg, code=code, code_verifier=code_verifier)
            access_token = token_data.get("access_token")
            if not access_token:
                raise RuntimeError(f"Token response missing access_token: {token_data}")

            # Don't print full token; just a fingerprint.
            token_fp = hashlib.sha256(access_token.encode("utf-8")).hexdigest()[:12]
            print(f"Obtained access token (sha256[:12]={token_fp}).")

            _call_api(http, args.api_base_url, access_token)

        return 0

    finally:
        try:
            server.shutdown()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
