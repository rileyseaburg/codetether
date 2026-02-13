# Unit tests for API key scope enforcement.

package api_keys_test

import rego.v1

import data.api_keys

# ── Test data ────────────────────────────────────────────────────

mock_api_key_user := {
    "user_id": "user-7",
    "roles": ["editor"],
    "tenant_id": "tenant-1",
    "scopes": ["tasks:read", "tasks:write"],
    "auth_source": "api_key",
}

mock_api_key_readonly := {
    "user_id": "user-8",
    "roles": ["editor"],
    "tenant_id": "tenant-1",
    "scopes": ["tasks:read"],
    "auth_source": "api_key",
}

mock_api_key_wildcard := {
    "user_id": "user-9",
    "roles": ["editor"],
    "tenant_id": "tenant-1",
    "scopes": ["tasks:*"],
    "auth_source": "api_key",
}

mock_jwt_user := {
    "user_id": "user-10",
    "roles": ["editor"],
    "tenant_id": "tenant-1",
    "scopes": [],
    "auth_source": "keycloak",
}

# ── API key scope tests ─────────────────────────────────────────

test_api_key_allowed_in_scope if {
    api_keys.allow with input as {"user": mock_api_key_user, "action": "tasks:read", "resource": {}}
}

test_api_key_write_allowed if {
    api_keys.allow with input as {"user": mock_api_key_user, "action": "tasks:write", "resource": {}}
}

test_api_key_readonly_denied_write if {
    not api_keys.allow with input as {"user": mock_api_key_readonly, "action": "tasks:write", "resource": {}}
}

test_api_key_readonly_allowed_read if {
    api_keys.allow with input as {"user": mock_api_key_readonly, "action": "tasks:read", "resource": {}}
}

test_api_key_denied_unscoped_action if {
    not api_keys.allow with input as {"user": mock_api_key_user, "action": "admin:access", "resource": {}}
}

# ── Wildcard scope tests ────────────────────────────────────────

test_wildcard_covers_read if {
    api_keys.allow with input as {"user": mock_api_key_wildcard, "action": "tasks:read", "resource": {}}
}

test_wildcard_covers_write if {
    api_keys.allow with input as {"user": mock_api_key_wildcard, "action": "tasks:write", "resource": {}}
}

test_wildcard_covers_execute if {
    api_keys.allow with input as {"user": mock_api_key_wildcard, "action": "tasks:execute", "resource": {}}
}

test_wildcard_no_cross_resource if {
    not api_keys.allow with input as {"user": mock_api_key_wildcard, "action": "codebases:read", "resource": {}}
}

# ── JWT user bypasses scope check ────────────────────────────────

test_jwt_user_no_scope_restriction if {
    api_keys.allow with input as {"user": mock_jwt_user, "action": "tasks:write", "resource": {}}
}
