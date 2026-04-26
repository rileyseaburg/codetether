# Agent Provenance Framework policy helpers.
#
# This package mirrors the Python prototype in a Rego-friendly form so OPA
# sidecars can reason about APF claims carried in input.provenance.

package provenance

import rego.v1

default allow := false

dimensions := ["origin", "inputs", "delegation", "runtime", "output"]

sensitive_actions := {
    "admin:access",
    "admin:manage_users",
    "admin:manage_tenants",
    "admin:manage_policies",
    "tasks:execute",
    "codebases:write",
    "codebases:delete",
    "workers:write",
    "workers:delete",
    "agent:execute",
    "agent:write",
    "mcp:write",
    "email:write",
    "voice:write",
}

taint_blocked_actions := {
    "untrusted-external": {
        "email:write",
        "mcp:write",
        "agent:execute",
        "tasks:execute",
        "codebases:write",
        "codebases:delete",
        "workers:write",
    },
    "external-mcp": {
        "email:write",
        "mcp:write",
        "agent:execute",
        "tasks:execute",
    },
}

# Legacy/no-provenance requests remain compatible. If any APF claim is present,
# failures become deny conditions.
allow if {
    not has_provenance
}

allow if {
    has_provenance
    count(reasons) == 0
}

has_provenance if {
    count(object.keys(object.get(input, "provenance", {}))) > 0
}

complete if {
    has_provenance
    count(missing_dimensions) == 0
    not input.provenance.ap_partial
}

missing_dimensions contains "origin" if {
    has_provenance
    not input.provenance.ap_origin.intent_hash
}

missing_dimensions contains "inputs" if {
    has_provenance
    not is_array(input.provenance.ap_inputs)
}

missing_dimensions contains "delegation" if {
    has_provenance
    not valid_delegation_shape
}

missing_dimensions contains "runtime" if {
    has_provenance
    count(object.keys(object.get(input.provenance, "ap_runtime", {}))) == 0
}

missing_dimensions contains "output" if {
    has_provenance
    count(object.keys(object.get(input.provenance, "ap_output", {}))) == 0
}

valid_delegation_shape if {
    chain := input.provenance.ap_delegation.chain
    is_array(chain)
    count(chain) > 0
}

reasons contains "origin intent hash mismatch" if {
    has_provenance
    expected := input.resource.ap_session_state.origin_intent_hash
    expected != ""
    input.provenance.ap_origin.intent_hash != expected
}

reasons contains "taint stripping detected" if {
    has_provenance
    some required in object.get(input.resource.ap_session_state, "taints", [])
    not token_has_taint(required)
}

reasons contains sprintf("taint blocks action: %s", [sensitivity]) if {
    has_provenance
    some marker in input.provenance.ap_inputs
    sensitivity := marker.sensitivity
    input.action in taint_blocked_actions[sensitivity]
}

reasons contains "taint blocks action: external-mcp" if {
    has_provenance
    some marker in input.provenance.ap_inputs
    endswith(marker.source, "external-mcp-server")
    input.action in taint_blocked_actions["external-mcp"]
}

reasons contains reason if {
    has_provenance
    some dimension in missing_dimensions
    reason := sprintf("missing %s provenance", [dimension])
}

reasons contains "partial provenance not permitted for sensitive action" if {
    has_provenance
    input.action in sensitive_actions
    not complete
}

reasons contains "action outside delegated capability envelope" if {
    has_provenance
    valid_delegation_shape
    chain := input.provenance.ap_delegation.chain
    current := chain[count(chain) - 1].capability
    not current.root
    not input.action in current.operations
}

reasons contains "delegation operations not attenuated" if {
    has_provenance
    some i
    chain := input.provenance.ap_delegation.chain
    i < count(chain) - 1
    parent := chain[i].capability
    child := chain[i + 1].capability
    not parent.root
    some op in child.operations
    not op in parent.operations
}

reasons contains "delegation spawn depth not attenuated" if {
    has_provenance
    some i
    chain := input.provenance.ap_delegation.chain
    i < count(chain) - 1
    parent := chain[i].capability
    child := chain[i + 1].capability
    not parent.root
    is_number(parent.spawn.max_depth)
    is_number(child.spawn.max_depth)
    child.spawn.max_depth > max([parent.spawn.max_depth - 1, 0])
}

reasons contains "delegation spawn fanout not attenuated" if {
    has_provenance
    some i
    chain := input.provenance.ap_delegation.chain
    i < count(chain) - 1
    parent := chain[i].capability
    child := chain[i + 1].capability
    not parent.root
    is_number(parent.spawn.max_fanout)
    is_number(child.spawn.max_fanout)
    child.spawn.max_fanout > parent.spawn.max_fanout
}

reasons contains sprintf("delegation budget not attenuated: %s", [key]) if {
    has_provenance
    some i
    chain := input.provenance.ap_delegation.chain
    i < count(chain) - 1
    parent := chain[i].capability
    child := chain[i + 1].capability
    not parent.root
    some key, child_value in child.budget
    parent_value := parent.budget[key]
    is_number(parent_value)
    is_number(child_value)
    child_value > parent_value
}

token_has_taint(required) if {
    some marker in input.provenance.ap_inputs
    marker.id == required.id
    marker.source == required.source
    marker.applied_at_turn == required.applied_at_turn
}
