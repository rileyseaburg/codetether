package provenance_test

import rego.v1

import data.provenance

base_provenance := {
    "ap_origin": {"intent_hash": "sha384:origin"},
    "ap_inputs": [],
    "ap_delegation": {
        "chain": [
            {"principal": "human:riley", "capability": {"root": true}},
            {
                "principal": "agent:builder",
                "capability": {
                    "operations": ["tasks:read", "tasks:write", "agent:execute"],
                    "budget": {"max_tool_calls": 10},
                    "spawn": {"max_depth": 1, "max_fanout": 2},
                },
            },
        ],
    },
    "ap_runtime": {"attestation_signature": "sig"},
    "ap_output": {"attestation_quote": "quote"},
}

test_complete_provenance_allows if {
    provenance.allow with input as {"action": "tasks:write", "resource": {}, "provenance": base_provenance}
}

test_action_outside_envelope_denied if {
    not provenance.allow with input as {"action": "mcp:write", "resource": {}, "provenance": base_provenance}
}

test_origin_mismatch_denied if {
    not provenance.allow with input as {
        "action": "tasks:write",
        "resource": {"ap_session_state": {"origin_intent_hash": "sha384:other"}},
        "provenance": base_provenance,
    }
}

test_taint_stripping_denied if {
    marker := {"id": "t1", "source": "urn:ap:taint:source:web-fetch", "applied_at_turn": 3}
    not provenance.allow with input as {
        "action": "tasks:write",
        "resource": {"ap_session_state": {"taints": [marker]}},
        "provenance": base_provenance,
    }
}

test_untrusted_taint_blocks_sensitive_action if {
    marker := {
        "id": "t1",
        "source": "urn:ap:taint:source:web-fetch",
        "sensitivity": "untrusted-external",
        "applied_at_turn": 3,
    }
    tainted := object.union(base_provenance, {"ap_inputs": [marker]})
    not provenance.allow with input as {"action": "agent:execute", "resource": {}, "provenance": tainted}
}

test_partial_provenance_denied_for_sensitive_action if {
    partial := object.union(base_provenance, {"ap_runtime": {}, "ap_partial": true})
    not provenance.allow with input as {"action": "agent:execute", "resource": {}, "provenance": partial}
}

test_legacy_without_provenance_allows if {
    provenance.allow with input as {"action": "tasks:write", "resource": {}, "provenance": {}}
}
