"""Conversion between identity receipts and persisted binding rows."""

from collections.abc import Mapping

from a2a_server.agent_identity_binding import AgentIdentityBinding


_RECEIPT_FIELDS = (
    'provisioning_id',
    'persona_id',
    'spiffe_id',
    'keycloak_subject',
    'keycloak_realm',
    'realm_roles',
    'groups',
    'opa_policy_binding_id',
    'opa_policy_revision',
    'provenance_id',
)
_ROW_FIELDS = (
    'provisioning_id',
    'persona_id',
    'spiffe_id',
    'keycloak_subject',
    'keycloak_realm',
    'roles',
    'groups',
    'policy_binding_id',
    'policy_revision',
    'provenance_id',
)


def values(receipt: dict[str, object]) -> list[object]:
    """Return receipt values in the binding insert order."""
    return [receipt[field] for field in _RECEIPT_FIELDS]


def matches(row: Mapping[str, object], expected: list[object]) -> bool:
    """Require every immutable field to match an idempotent replay."""
    pairs = zip(_ROW_FIELDS, expected, strict=True)
    return all(row[field] == value for field, value in pairs)


def binding(row: Mapping[str, object]) -> AgentIdentityBinding:
    """Convert a database record into its typed policy binding."""
    fields = AgentIdentityBinding.__dataclass_fields__
    return AgentIdentityBinding(**{field: row[field] for field in fields})
