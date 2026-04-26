"""Agent Provenance Framework helpers.

This module implements the first policy-enforcement slice of the RFC draft in
``rfc/Agent-Provenance-Framework_for_Autonomous-Multi-Agent-Systems.txt``.
It intentionally focuses on deterministic, local verification that can be fed
into OPA and Python policy checks:

* origin immutability against session state
* monotonic taint propagation / taint stripping detection
* delegation capability attenuation
* current action constrained by the immediate caller capability envelope
* partial-provenance handling for sensitive actions

Runtime and output attestation are represented as required dimensions, but this
prototype only verifies presence unless deployment-specific attestation metadata
is supplied later.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

PROVENANCE_DIMENSIONS = ("origin", "inputs", "delegation", "runtime", "output")

DEFAULT_SENSITIVE_ACTIONS: Set[str] = {
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

DEFAULT_TAINT_BLOCKED_ACTIONS: Dict[str, Set[str]] = {
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


@dataclass(frozen=True)
class ProvenanceDecision:
    """Result of provenance verification for one action request."""

    complete: bool
    dimensions: Dict[str, bool]
    missing_dimensions: List[str] = field(default_factory=list)
    failures: List[str] = field(default_factory=list)
    partial: bool = False

    @property
    def allowed_by_provenance(self) -> bool:
        return not self.failures

    def as_dict(self) -> Dict[str, Any]:
        return {
            "complete": self.complete,
            "dimensions": self.dimensions,
            "missing_dimensions": self.missing_dimensions,
            "failures": self.failures,
            "partial": self.partial,
        }


def verify_provenance(
    provenance: Optional[Dict[str, Any]],
    action: str,
    resource: Optional[Dict[str, Any]] = None,
    *,
    sensitive_actions: Optional[Iterable[str]] = None,
    taint_blocked_actions: Optional[Dict[str, Iterable[str]]] = None,
) -> ProvenanceDecision:
    """Verify provenance claims for a policy decision.

    ``provenance`` is expected to use the RFC claim names (``ap_origin``,
    ``ap_inputs``, etc.). ``resource`` may contain authoritative session state:

    * ``ap_session_state.origin_intent_hash`` or ``session_origin_intent_hash``
    * ``ap_session_state.taints`` or ``session_taints``

    Absence of provenance is treated as legacy/no-provenance and allowed by this
    function. When any provenance claim is present, the action is evaluated under
    the framework rules.
    """

    resource = resource or {}
    if not provenance:
        return ProvenanceDecision(
            complete=False,
            dimensions={dim: False for dim in PROVENANCE_DIMENSIONS},
            missing_dimensions=list(PROVENANCE_DIMENSIONS),
            partial=True,
        )

    failures: List[str] = []
    dimensions = {dim: False for dim in PROVENANCE_DIMENSIONS}

    origin = provenance.get("ap_origin")
    if isinstance(origin, dict) and origin.get("intent_hash"):
        dimensions["origin"] = True
        expected = _session_origin_hash(resource)
        if expected and origin.get("intent_hash") != expected:
            failures.append("origin intent hash mismatch")

    inputs = provenance.get("ap_inputs")
    if isinstance(inputs, list):
        dimensions["inputs"] = True
        missing_taints = _missing_session_taints(inputs, _session_taints(resource))
        if missing_taints:
            failures.append("taint stripping detected")
        blocked = _taint_blocks_action(inputs, action, taint_blocked_actions)
        if blocked:
            failures.append(f"taint blocks action: {blocked}")

    delegation = provenance.get("ap_delegation")
    if _valid_delegation_shape(delegation):
        dimensions["delegation"] = True
        failures.extend(_delegation_failures(delegation, action))

    runtime = provenance.get("ap_runtime")
    if isinstance(runtime, dict) and runtime:
        dimensions["runtime"] = True

    output = provenance.get("ap_output")
    if isinstance(output, dict) and output:
        dimensions["output"] = True

    missing_dimensions = [dim for dim, ok in dimensions.items() if not ok]
    partial = bool(provenance.get("ap_partial")) or bool(missing_dimensions)
    complete = not partial

    sensitive = set(sensitive_actions or DEFAULT_SENSITIVE_ACTIONS)
    if partial and action in sensitive:
        failures.append("partial provenance not permitted for sensitive action")

    return ProvenanceDecision(
        complete=complete,
        dimensions=dimensions,
        missing_dimensions=missing_dimensions,
        failures=failures,
        partial=partial,
    )


def _session_origin_hash(resource: Dict[str, Any]) -> Optional[str]:
    state = resource.get("ap_session_state") or {}
    return state.get("origin_intent_hash") or resource.get("session_origin_intent_hash")


def _session_taints(resource: Dict[str, Any]) -> List[Dict[str, Any]]:
    state = resource.get("ap_session_state") or {}
    return state.get("taints") or resource.get("session_taints") or []


def _taint_id(marker: Dict[str, Any]) -> Tuple[Any, Any, Any]:
    return (marker.get("id"), marker.get("source"), marker.get("applied_at_turn"))


def _missing_session_taints(
    token_taints: List[Dict[str, Any]], session_taints: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    token_ids = {_taint_id(t) for t in token_taints if isinstance(t, dict)}
    return [t for t in session_taints if isinstance(t, dict) and _taint_id(t) not in token_ids]


def _taint_blocks_action(
    inputs: List[Dict[str, Any]],
    action: str,
    configured: Optional[Dict[str, Iterable[str]]],
) -> Optional[str]:
    if configured is None:
        blocked_map = DEFAULT_TAINT_BLOCKED_ACTIONS
    else:
        blocked_map = {key: set(value) for key, value in configured.items()}
    for marker in inputs:
        if not isinstance(marker, dict):
            continue
        sensitivity = marker.get("sensitivity")
        source = marker.get("source", "")
        candidate_keys = [sensitivity]
        if source.endswith("external-mcp-server"):
            candidate_keys.append("external-mcp")
        for key in candidate_keys:
            if key in blocked_map and action in blocked_map[key]:
                return str(key)
    return None


def _valid_delegation_shape(delegation: Any) -> bool:
    return isinstance(delegation, dict) and isinstance(delegation.get("chain"), list) and bool(delegation["chain"])


def _delegation_failures(delegation: Dict[str, Any], action: str) -> List[str]:
    failures: List[str] = []
    chain = delegation["chain"]

    for parent, child in zip(chain, chain[1:]):
        parent_cap = parent.get("capability", {}) if isinstance(parent, dict) else {}
        child_cap = child.get("capability", {}) if isinstance(child, dict) else {}
        failures.extend(_attenuation_failures(parent_cap, child_cap))

    current_cap = chain[-1].get("capability", {}) if isinstance(chain[-1], dict) else {}
    if not current_cap.get("root"):
        operations = set(current_cap.get("operations") or [])
        if action not in operations:
            failures.append("action outside delegated capability envelope")
    return failures


def _attenuation_failures(parent: Dict[str, Any], child: Dict[str, Any]) -> List[str]:
    if parent.get("root"):
        return []

    failures: List[str] = []
    parent_ops = set(parent.get("operations") or [])
    child_ops = set(child.get("operations") or [])
    if not child_ops.issubset(parent_ops):
        failures.append("delegation operations not attenuated")

    parent_budget = parent.get("budget") or {}
    child_budget = child.get("budget") or {}
    for key, parent_value in parent_budget.items():
        if not isinstance(parent_value, (int, float)):
            continue
        child_value = child_budget.get(key)
        if not isinstance(child_value, (int, float)) or child_value > parent_value:
            failures.append(f"delegation budget not attenuated: {key}")

    parent_spawn = parent.get("spawn") or {}
    child_spawn = child.get("spawn") or {}
    parent_depth = parent_spawn.get("max_depth")
    child_depth = child_spawn.get("max_depth")
    if isinstance(parent_depth, int) and isinstance(child_depth, int):
        if child_depth > parent_depth - 1:
            failures.append("delegation spawn depth not attenuated")
    parent_fanout = parent_spawn.get("max_fanout")
    child_fanout = child_spawn.get("max_fanout")
    if isinstance(parent_fanout, int) and isinstance(child_fanout, int):
        if child_fanout > parent_fanout:
            failures.append("delegation spawn fanout not attenuated")

    parent_constraints = parent.get("constraints") or {}
    child_constraints = child.get("constraints") or {}
    for operation in child_ops:
        if operation in parent_constraints and operation not in child_constraints:
            failures.append(f"delegation constraints missing for {operation}")

    return failures
