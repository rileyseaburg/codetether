# Unit tests for authorization policies.
#
# Run with: opa test policies/ -v

package authz_test

import rego.v1

import data.authz

# ── Test data ────────────────────────────────────────────────────

mock_admin := {
    "user_id": "user-1",
    "roles": ["admin"],
    "tenant_id": "tenant-1",
    "scopes": [],
    "auth_source": "keycloak",
}

mock_a2a_admin := {
    "user_id": "user-2",
    "roles": ["a2a-admin"],
    "tenant_id": "tenant-1",
    "scopes": [],
    "auth_source": "keycloak",
}

mock_operator := {
    "user_id": "user-3",
    "roles": ["operator"],
    "tenant_id": "tenant-1",
    "scopes": [],
    "auth_source": "keycloak",
}

mock_editor := {
    "user_id": "user-4",
    "roles": ["editor"],
    "tenant_id": "tenant-1",
    "scopes": [],
    "auth_source": "keycloak",
}

mock_viewer := {
    "user_id": "user-5",
    "roles": ["viewer"],
    "tenant_id": "tenant-1",
    "scopes": [],
    "auth_source": "keycloak",
}

mock_no_roles := {
    "user_id": "user-6",
    "roles": [],
    "tenant_id": "tenant-1",
    "scopes": [],
    "auth_source": "keycloak",
}

# ── Admin tests ──────────────────────────────────────────────────

test_admin_can_access_admin if {
    authz.allow with input as {"user": mock_admin, "action": "admin:access", "resource": {}}
}

test_admin_can_write_tasks if {
    authz.allow with input as {"user": mock_admin, "action": "tasks:write", "resource": {}}
}

test_admin_can_delete_codebases if {
    authz.allow with input as {"user": mock_admin, "action": "codebases:delete", "resource": {}}
}

# ── a2a-admin inherits admin ────────────────────────────────────

test_a2a_admin_inherits_admin if {
    authz.allow with input as {"user": mock_a2a_admin, "action": "admin:access", "resource": {}}
}

test_a2a_admin_can_manage_users if {
    authz.allow with input as {"user": mock_a2a_admin, "action": "admin:manage_users", "resource": {}}
}

# ── Operator tests ───────────────────────────────────────────────

test_operator_can_read_tasks if {
    authz.allow with input as {"user": mock_operator, "action": "tasks:read", "resource": {}}
}

test_operator_can_write_workers if {
    authz.allow with input as {"user": mock_operator, "action": "workers:write", "resource": {}}
}

test_operator_cannot_admin if {
    not authz.allow with input as {"user": mock_operator, "action": "admin:access", "resource": {}}
}

test_operator_cannot_delete_tasks if {
    not authz.allow with input as {"user": mock_operator, "action": "tasks:delete", "resource": {}}
}

# ── Editor tests ─────────────────────────────────────────────────

test_editor_can_write_tasks if {
    authz.allow with input as {"user": mock_editor, "action": "tasks:write", "resource": {}}
}

test_editor_can_execute_agent if {
    authz.allow with input as {"user": mock_editor, "action": "agent:execute", "resource": {}}
}

test_editor_cannot_admin if {
    not authz.allow with input as {"user": mock_editor, "action": "admin:access", "resource": {}}
}

test_editor_cannot_delete_tasks if {
    not authz.allow with input as {"user": mock_editor, "action": "tasks:delete", "resource": {}}
}

test_editor_cannot_write_workers if {
    not authz.allow with input as {"user": mock_editor, "action": "workers:write", "resource": {}}
}

# ── Viewer tests ─────────────────────────────────────────────────

test_viewer_can_read_tasks if {
    authz.allow with input as {"user": mock_viewer, "action": "tasks:read", "resource": {}}
}

test_viewer_can_read_monitor if {
    authz.allow with input as {"user": mock_viewer, "action": "monitor:read", "resource": {}}
}

test_viewer_cannot_write_tasks if {
    not authz.allow with input as {"user": mock_viewer, "action": "tasks:write", "resource": {}}
}

test_viewer_cannot_execute_agent if {
    not authz.allow with input as {"user": mock_viewer, "action": "agent:execute", "resource": {}}
}

# ── No-role user ─────────────────────────────────────────────────

test_no_roles_denied if {
    not authz.allow with input as {"user": mock_no_roles, "action": "tasks:read", "resource": {}}
}

# ── Public endpoints ─────────────────────────────────────────────

test_public_endpoint_allowed_no_roles if {
    authz.allow with input as {"user": mock_no_roles, "action": "health", "resource": {}}
}

test_public_endpoint_allowed_for_login if {
    authz.allow with input as {"user": mock_no_roles, "action": "auth:login", "resource": {}}
}
