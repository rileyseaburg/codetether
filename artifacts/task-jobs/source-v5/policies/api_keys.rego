# API key scope enforcement policy.
#
# When the auth source is "api_key", the requested action must be
# within the key's granted scopes.  JWT-authenticated users are
# not subject to scope restrictions (they use role-based access).

package api_keys

import rego.v1

import data.authz

default allow := false

# Non-API-key users bypass scope checks entirely.
allow if {
    input.user.auth_source != "api_key"
    authz.allow
}

# API key users: action must be allowed by role AND within key scopes.
allow if {
    input.user.auth_source == "api_key"
    authz.allow
    _scope_permits
}

# A scope permits the action when:
#   - The exact action is in the scopes list, OR
#   - A wildcard scope (e.g. "tasks:*") covers the action's resource type.
_scope_permits if {
    input.action in input.user.scopes
}

_scope_permits if {
    parts := split(input.action, ":")
    count(parts) == 2
    wildcard := concat(":", [parts[0], "*"])
    wildcard in input.user.scopes
}

# ── Deny reasons ─────────────────────────────────────────────────

reasons contains "api key scope does not permit action" if {
    input.user.auth_source == "api_key"
    not _scope_permits
}

reasons contains reason if {
    some reason in authz.reasons
}
