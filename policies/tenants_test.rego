# Unit tests for tenant isolation policy.

package tenants_test

import rego.v1

import data.tenants

# ── Test data ────────────────────────────────────────────────────

mock_user_t1 := {
    "user_id": "user-11",
    "roles": ["editor"],
    "tenant_id": "tenant-1",
    "scopes": [],
    "auth_source": "keycloak",
}

mock_user_t2 := {
    "user_id": "user-12",
    "roles": ["editor"],
    "tenant_id": "tenant-2",
    "scopes": [],
    "auth_source": "keycloak",
}

mock_admin := {
    "user_id": "user-13",
    "roles": ["admin"],
    "tenant_id": "tenant-1",
    "scopes": [],
    "auth_source": "keycloak",
}

resource_t1 := {
    "type": "task",
    "id": "task-1",
    "owner_id": "user-11",
    "tenant_id": "tenant-1",
}

resource_t2 := {
    "type": "task",
    "id": "task-2",
    "owner_id": "user-12",
    "tenant_id": "tenant-2",
}

resource_no_tenant := {
    "type": "task",
    "id": "task-3",
    "owner_id": "user-11",
}

# ── Same tenant access ──────────────────────────────────────────

test_same_tenant_allowed if {
    tenants.allow with input as {"user": mock_user_t1, "action": "tasks:read", "resource": resource_t1}
}

# ── Cross tenant denied ─────────────────────────────────────────

test_cross_tenant_denied if {
    not tenants.allow with input as {"user": mock_user_t1, "action": "tasks:read", "resource": resource_t2}
}

test_cross_tenant_denied_reverse if {
    not tenants.allow with input as {"user": mock_user_t2, "action": "tasks:read", "resource": resource_t1}
}

# ── Admin cross-tenant access ───────────────────────────────────

test_admin_cross_tenant_allowed if {
    tenants.allow with input as {"user": mock_admin, "action": "tasks:read", "resource": resource_t2}
}

# ── No tenant context ───────────────────────────────────────────

test_no_resource_tenant_defers_to_authz if {
    tenants.allow with input as {"user": mock_user_t1, "action": "tasks:read", "resource": resource_no_tenant}
}

# ── Ownership tests ─────────────────────────────────────────────

test_owner_can_mutate if {
    tenants.allow_mutation with input as {"user": mock_user_t1, "action": "tasks:write", "resource": resource_t1}
}

test_non_owner_cannot_mutate if {
    not tenants.allow_mutation with input as {"user": mock_user_t2, "action": "tasks:write", "resource": resource_t1}
}

test_admin_can_mutate_any if {
    tenants.allow_mutation with input as {"user": mock_admin, "action": "tasks:write", "resource": resource_t2}
}

# ── Deny reasons ─────────────────────────────────────────────────

test_cross_tenant_reason if {
    reasons := tenants.reasons with input as {"user": mock_user_t1, "action": "tasks:read", "resource": resource_t2}
    "cross-tenant access denied" in reasons
}

test_not_owner_reason if {
    reasons := tenants.reasons with input as {"user": mock_user_t2, "action": "tasks:write", "resource": resource_t1}
    "not resource owner" in reasons
}
