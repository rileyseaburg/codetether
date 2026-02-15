#!/usr/bin/env python3
"""
Add localhost:3001 redirect URIs to the Keycloak a2a-monitor client.
This ADDS to existing URIs, does not replace them.
"""

import requests
import json
import sys

KEYCLOAK_URL = "https://auth.quantum-forge.io"
REALM = "quantum-forge"
CLIENT_ID = "a2a-monitor"
USERNAME = "info@evolvingsoftware.io"
PASSWORD = "Spr!ng20@4"

# New URIs to add (includes HTTPS for development)
NEW_REDIRECT_URIS = [
    "http://localhost:3001/api/auth/*",
    "http://127.0.0.1:3001/api/auth/*",
    "https://192.168.50.101:3001/api/auth/*",
    "https://a2a.quantum-forge.net/api/auth/*",
]
NEW_WEB_ORIGINS = [
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "https://192.168.50.101:3001",
    "https://a2a.quantum-forge.net",
]


def get_token(realm: str) -> str:
    """Get admin token from specified realm."""
    resp = requests.post(
        f"{KEYCLOAK_URL}/realms/{realm}/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": USERNAME,
            "password": PASSWORD,
        },
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def main():
    # Try master realm first for admin access
    print("Getting admin token from master realm...")
    try:
        token = get_token("master")
    except Exception as e:
        print(f"Master realm failed: {e}, trying quantum-forge realm...")
        token = get_token(REALM)

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Get client by clientId
    print(f"Looking up client '{CLIENT_ID}'...")
    resp = requests.get(
        f"{KEYCLOAK_URL}/admin/realms/{REALM}/clients",
        params={"clientId": CLIENT_ID},
        headers=headers,
    )
    resp.raise_for_status()
    clients = resp.json()

    if not clients:
        print(f"Client '{CLIENT_ID}' not found!")
        sys.exit(1)

    client = clients[0]
    client_uuid = client["id"]
    print(f"Found client UUID: {client_uuid}")

    # Get current redirect URIs and web origins
    current_redirects = client.get("redirectUris", [])
    current_origins = client.get("webOrigins", [])

    print(f"Current redirectUris: {current_redirects}")
    print(f"Current webOrigins: {current_origins}")

    # Add new URIs (avoid duplicates)
    updated_redirects = list(set(current_redirects + NEW_REDIRECT_URIS))
    updated_origins = list(set(current_origins + NEW_WEB_ORIGINS))

    print(f"Updated redirectUris: {updated_redirects}")
    print(f"Updated webOrigins: {updated_origins}")

    # Patch the client
    patch_data = {
        "redirectUris": updated_redirects,
        "webOrigins": updated_origins,
    }

    print("Updating client...")
    resp = requests.put(
        f"{KEYCLOAK_URL}/admin/realms/{REALM}/clients/{client_uuid}",
        headers=headers,
        json={**client, **patch_data},
    )
    resp.raise_for_status()

    print("✅ Client updated successfully!")
    print(f"Added redirect URIs: {NEW_REDIRECT_URIS}")
    print(f"Added web origins: {NEW_WEB_ORIGINS}")


if __name__ == "__main__":
    main()
