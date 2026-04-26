"""Tests for Agent Provenance Framework policy integration."""

import os

import pytest

os.environ["OPA_LOCAL_MODE"] = "true"

from a2a_server.policy import check_policy, _build_input, _evaluate_local
from a2a_server.provenance import verify_provenance


def agent_user(provenance=None):
    return {
        "id": "agent-1",
        "user_id": "agent-1",
        "email": "agent@test.com",
        "roles": ["a2a-agent"],
        "tenant_id": "tenant-1",
        "provenance": provenance or complete_provenance(),
    }


def taint_marker():
    return {
        "id": "taint-1",
        "source": "urn:ap:taint:source:web-fetch",
        "sensitivity": "untrusted-external",
        "applied_at": "2026-04-20T14:12:00Z",
        "applied_at_turn": 3,
        "scope": "session",
    }


def complete_provenance(**overrides):
    value = {
        "ap_origin": {
            "intent_hash": "sha384:origin",
            "intent_classification": "urn:ap:intent:code-maintenance",
            "session_started_at": "2026-04-20T14:00:00Z",
        },
        "ap_session": {"id": "session-1", "turn": 7, "parent_jti": "turn-6"},
        "ap_inputs": [],
        "ap_delegation": {
            "chain": [
                {
                    "principal": "human:riley@example.test",
                    "issuer": "https://idp.example.test/",
                    "capability": {"root": True},
                },
                {
                    "principal": "spiffe://codetether.local/agent/builder",
                    "issuer": "https://as.codetether.local/",
                    "capability": {
                        "operations": ["tasks:read", "tasks:write", "agent:execute"],
                        "budget": {"max_tool_calls": 10},
                        "spawn": {"max_depth": 1, "max_fanout": 2},
                    },
                },
            ]
        },
        "ap_runtime": {
            "model": "test-model",
            "model_provider": "test-provider",
            "system_prompt_hash": "sha384:system",
            "tool_manifest_hash": "sha384:tools",
            "config_hash": "sha384:config",
            "attestation_type": "service-level",
            "attestation_signature": "sig",
        },
        "ap_output": {
            "input_context_hash": "sha384:ctx",
            "output_prefix_hash": "sha384:prefix",
            "tool_call_hash": "sha384:tool",
            "attestation_quote": "quote",
        },
    }
    value.update(overrides)
    return value


class TestProvenanceVerifier:
    def test_complete_provenance_allows_declared_action(self):
        decision = verify_provenance(complete_provenance(), "tasks:write")
        assert decision.allowed_by_provenance
        assert decision.complete
        assert decision.missing_dimensions == []

    def test_origin_mismatch_fails(self):
        resource = {"ap_session_state": {"origin_intent_hash": "sha384:original"}}
        decision = verify_provenance(complete_provenance(), "tasks:write", resource)
        assert not decision.allowed_by_provenance
        assert "origin intent hash mismatch" in decision.failures

    def test_malformed_origin_fails_without_crashing(self):
        decision = verify_provenance(
            complete_provenance(ap_origin="not-a-dict"),
            "tasks:write",
        )
        assert not decision.allowed_by_provenance
        assert "missing origin provenance" in decision.failures

    def test_legacy_origin_hash_field_fails_on_mismatch(self):
        resource = {"session_origin_intent_hash": "sha384:original"}
        decision = verify_provenance(complete_provenance(), "tasks:write", resource)
        assert not decision.allowed_by_provenance
        assert "origin intent hash mismatch" in decision.failures

    def test_taint_stripping_fails(self):
        resource = {"ap_session_state": {"taints": [taint_marker()]}}
        decision = verify_provenance(complete_provenance(ap_inputs=[]), "tasks:write", resource)
        assert not decision.allowed_by_provenance
        assert "taint stripping detected" in decision.failures

    def test_legacy_session_taints_field_detects_stripping(self):
        resource = {"session_taints": [taint_marker()]}
        decision = verify_provenance(complete_provenance(ap_inputs=[]), "tasks:write", resource)
        assert not decision.allowed_by_provenance
        assert "taint stripping detected" in decision.failures

    def test_untrusted_taint_blocks_external_write_action(self):
        decision = verify_provenance(
            complete_provenance(ap_inputs=[taint_marker()]),
            "agent:execute",
        )
        assert not decision.allowed_by_provenance
        assert "taint blocks action: untrusted-external" in decision.failures

    def test_delegation_must_attenuate_operations(self):
        provenance = complete_provenance(
            ap_delegation={
                "chain": [
                    {
                        "principal": "agent:parent",
                        "capability": {
                            "operations": ["tasks:read"],
                            "spawn": {"max_depth": 1},
                        },
                    },
                    {
                        "principal": "agent:child",
                        "capability": {
                            "operations": ["tasks:read", "tasks:write"],
                            "spawn": {"max_depth": 1},
                        },
                    },
                ]
            }
        )
        decision = verify_provenance(provenance, "tasks:write")
        assert not decision.allowed_by_provenance
        assert "delegation operations not attenuated" in decision.failures
        assert "delegation spawn depth not attenuated" in decision.failures

    def test_zero_spawn_depth_parent_cannot_delegate_zero_depth_child(self):
        provenance = complete_provenance(
            ap_delegation={
                "chain": [
                    {
                        "principal": "agent:parent",
                        "capability": {
                            "operations": ["tasks:write"],
                            "spawn": {"max_depth": 0},
                        },
                    },
                    {
                        "principal": "agent:child",
                        "capability": {
                            "operations": ["tasks:write"],
                            "spawn": {"max_depth": 0},
                        },
                    },
                ]
            }
        )
        decision = verify_provenance(provenance, "tasks:write")
        assert not decision.allowed_by_provenance
        assert "delegation spawn depth not attenuated" in decision.failures

    def test_child_cannot_remove_parent_budget_limit(self):
        provenance = complete_provenance(
            ap_delegation={
                "chain": [
                    {
                        "principal": "agent:parent",
                        "capability": {
                            "operations": ["tasks:write"],
                            "budget": {"max_tool_calls": 10},
                        },
                    },
                    {
                        "principal": "agent:child",
                        "capability": {
                            "operations": ["tasks:write"],
                            "budget": {},
                        },
                    },
                ]
            }
        )
        decision = verify_provenance(provenance, "tasks:write")
        assert not decision.allowed_by_provenance
        assert "delegation budget not attenuated: max_tool_calls" in decision.failures

    def test_partial_provenance_denied_for_sensitive_action(self):
        provenance = complete_provenance(ap_runtime={}, ap_partial=True)
        decision = verify_provenance(provenance, "agent:execute")
        assert not decision.allowed_by_provenance
        assert "partial provenance not permitted for sensitive action" in decision.failures


class TestPolicyIntegration:
    @pytest.mark.asyncio
    async def test_policy_allows_agent_with_complete_provenance(self):
        assert await check_policy(agent_user(), "tasks:write")

    @pytest.mark.asyncio
    async def test_policy_denies_action_outside_capability_envelope(self):
        assert not await check_policy(agent_user(), "mcp:write")

    @pytest.mark.asyncio
    async def test_policy_denies_taint_blocked_action(self):
        user = agent_user(complete_provenance(ap_inputs=[taint_marker()]))
        assert not await check_policy(user, "agent:execute")

    @pytest.mark.asyncio
    async def test_policy_detects_taint_stripping_against_resource_state(self):
        resource = {
            "type": "task",
            "id": "t1",
            "tenant_id": "tenant-1",
            "ap_session_state": {"taints": [taint_marker()]},
        }
        assert not await check_policy(agent_user(), "tasks:write", resource)

    def test_opa_input_contains_provenance_claims(self):
        inp = _build_input(agent_user(), "tasks:write")
        assert inp["input"]["provenance"]["ap_origin"]["intent_hash"] == "sha384:origin"

    def test_local_reasons_include_provenance_failures(self):
        allowed, reasons = _evaluate_local(agent_user(), "mcp:write")
        assert not allowed
        assert "action outside delegated capability envelope" in reasons
