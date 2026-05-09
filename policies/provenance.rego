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
    ap_session_state := object.get(input.resource, "ap_session_state", {})
    ap_hash := object.get(ap_session_state, "origin_intent_hash", null)
    legacy_hash := object.get(input.resource, "session_origin_intent_hash", "")
    expected := _coalesce_origin_hash(ap_hash, legacy_hash)
    is_string(expected)
    expected != ""
    input.provenance.ap_origin.intent_hash != expected
}

# Coalesce null/empty ap_session_state.origin_intent_hash to the legacy field.
_coalesce_origin_hash(ap_hash, legacy_hash) := legacy_hash if {
    not is_string(ap_hash)
}
_coalesce_origin_hash(ap_hash, legacy_hash) := "" if {
    is_string(ap_hash)
    ap_hash == ""
}
_coalesce_origin_hash(ap_hash, _legacy_hash) := ap_hash if {
    is_string(ap_hash)
    ap_hash != ""
}

session_taints := _resolve_session_taints

_resolve_session_taints := legacy if {
    ap_session_state := object.get(input.resource, "ap_session_state", {})
    raw := object.get(ap_session_state, "taints", null)
    not _is_valid_taint_array(raw)
    legacy := object.get(input.resource, "session_taints", [])
    is_array(legacy)
}

_resolve_session_taints := raw if {
    ap_session_state := object.get(input.resource, "ap_session_state", {})
    raw := object.get(ap_session_state, "taints", null)
    _is_valid_taint_array(raw)
}

_resolve_session_taints := [] if {
    not _has_ap_taints
    not _has_legacy_taints
}

_is_valid_taint_array(v) if {
    is_array(v)
}

_has_ap_taints if {
    ap_session_state := object.get(input.resource, "ap_session_state", {})
    raw := object.get(ap_session_state, "taints", null)
    _is_valid_taint_array(raw)
}

_has_legacy_taints if {
    legacy := object.get(input.resource, "session_taints", null)
    is_array(legacy)
}

reasons contains "taint stripping detected" if {
    has_provenance
    some required in session_taints
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
    parent_depth := object.get(object.get(parent, "spawn", {}), "max_depth", null)
    child_depth := object.get(object.get(child, "spawn", {}), "max_depth", null)
    is_number(parent_depth)
    _child_depth_violation(parent_depth, child_depth)
}

_child_depth_violation(parent_depth, child_depth) if {
    not is_number(child_depth)
}

_child_depth_violation(parent_depth, child_depth) if {
    is_number(child_depth)
    child_depth > parent_depth - 1
}

reasons contains "delegation spawn fanout not attenuated" if {
    has_provenance
    some i
    chain := input.provenance.ap_delegation.chain
    i < count(chain) - 1
    parent := chain[i].capability
    child := chain[i + 1].capability
    not parent.root
    parent_fanout := object.get(object.get(parent, "spawn", {}), "max_fanout", null)
    child_fanout := object.get(object.get(child, "spawn", {}), "max_fanout", null)
    is_number(parent_fanout)
    not _fanout_attenuated(parent_fanout, child_fanout)
}

_fanout_attenuated(parent_fanout, child_fanout) if {
    is_number(child_fanout)
    child_fanout <= parent_fanout
}

reasons contains sprintf("delegation budget not attenuated: %s", [key]) if {
    has_provenance
    some i
    chain := input.provenance.ap_delegation.chain
    i < count(chain) - 1
    parent := chain[i].capability
    child := chain[i + 1].capability
    not parent.root
    some key, parent_value in parent.budget
    is_number(parent_value)
    not budget_key_attenuated(child, key, parent_value)
}

budget_key_attenuated(child, key, parent_value) if {
    child_budget := object.get(child, "budget", {})
    child_value := object.get(child_budget, key, null)
    is_number(child_value)
    child_value <= parent_value
}

token_has_taint(required) if {
    some marker in input.provenance.ap_inputs
    marker.id == required.id
    marker.source == required.source
    marker.applied_at_turn == required.applied_at_turn
}
