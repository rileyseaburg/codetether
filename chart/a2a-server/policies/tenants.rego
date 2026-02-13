# Tenant isolation policy.
#
# Ensures users can only access resources within their own tenant.
# Admins may bypass tenant restrictions for cross-tenant operations.

package tenants

import rego.v1

import data.authz

default allow := false

# No resource context provided — defer to base authz.
allow if {
    not input.resource.tenant_id
    authz.allow
}

# User has no tenant (e.g. global/system user) — defer to base authz.
allow if {
    not input.user.tenant_id
    authz.allow
}

# Matching tenant — allow if base authz passes.
allow if {
    input.resource.tenant_id == input.user.tenant_id
    authz.allow
}

# Admins may access resources in any tenant.
allow if {
    _is_admin
    authz.allow
}

_is_admin if {
    "admin" in authz.effective_roles
}

_is_admin if {
    "a2a-admin" in authz.effective_roles
}

# ── Resource ownership ───────────────────────────────────────────

# Check whether the user owns the resource.
is_owner if {
    input.resource.owner_id == input.user.user_id
}

# Non-admin users can only mutate resources they own.
allow_mutation if {
    allow
    is_owner
}

allow_mutation if {
    allow
    _is_admin
}

# ── Deny reasons ─────────────────────────────────────────────────

reasons contains "cross-tenant access denied" if {
    input.resource.tenant_id
    input.user.tenant_id
    input.resource.tenant_id != input.user.tenant_id
    not _is_admin
}

reasons contains "not resource owner" if {
    input.resource.owner_id
    input.user.user_id
    input.resource.owner_id != input.user.user_id
    not _is_admin
}
