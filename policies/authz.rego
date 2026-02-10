# Main authorization policy for A2A Server.
#
# Input schema:
#   input.user.user_id      - string: authenticated user ID
#   input.user.roles        - array[string]: Keycloak realm roles
#   input.user.tenant_id    - string|null: tenant the user belongs to
#   input.user.scopes       - array[string]: API-key scopes (empty for JWT users)
#   input.user.auth_source  - string: "keycloak" | "self-service" | "api_key"
#   input.action            - string: requested permission (e.g. "tasks:write")
#   input.resource.type     - string: resource type (e.g. "task")
#   input.resource.id       - string|null: resource ID
#   input.resource.owner_id - string|null: resource owner's user ID
#   input.resource.tenant_id- string|null: resource's tenant ID

package authz

import rego.v1

default allow := false

# ── Role → Permission mapping ───────────────────────────────────
# Built from data.json at OPA startup.

# Resolve role inheritance (e.g. a2a-admin inherits admin).
effective_roles contains role if {
    some role in input.user.roles
    not data.roles[role].inherits
}

effective_roles contains parent if {
    some role in input.user.roles
    parent := data.roles[role].inherits
}

# Collect all permissions granted by the user's effective roles.
role_permissions contains perm if {
    some role in effective_roles
    some perm in data.roles[role].permissions
}

# ── Core allow rules ────────────────────────────────────────────

# Rule 1: Public endpoints are always allowed.
allow if {
    input.action in data.public_endpoints
}

# Rule 2: Role-based access — user's roles grant the requested permission.
allow if {
    input.action in role_permissions
}

# ── Deny reasons (for decision logging) ─────────────────────────

reasons contains "no matching role permission" if {
    not input.action in role_permissions
    not input.action in data.public_endpoints
}

reasons contains "tenant mismatch" if {
    input.resource.tenant_id
    input.user.tenant_id
    input.resource.tenant_id != input.user.tenant_id
}
