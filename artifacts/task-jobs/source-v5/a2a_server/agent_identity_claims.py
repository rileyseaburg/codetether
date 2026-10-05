"""Validation of explicitly approved OPA roles and Keycloak groups."""

import json
import re

from a2a_server.policy import POLICIES_DIR


_CLAIM = re.compile(r'^[a-z0-9][a-z0-9._-]{0,62}$')
_FORBIDDEN = {'admin', 'a2a-admin'}


def normalize(
    roles: list[str], groups: list[str]
) -> tuple[list[str], list[str]]:
    """Validate authority independently from the selected persona."""
    normalized_roles = _claims(roles, 'role')
    normalized_groups = _claims(groups, 'group')
    unknown = set(normalized_roles) - set(data().get('roles', {}))
    forbidden = set(normalized_roles) & _FORBIDDEN
    if unknown:
        raise ValueError(f'roles are not defined by OPA: {sorted(unknown)}')
    if forbidden:
        raise ValueError(
            f'agents cannot receive admin roles: {sorted(forbidden)}'
        )
    return normalized_roles, normalized_groups


def managed_roles() -> list[str]:
    """Return every role whose Keycloak assignment is managed by OPA."""
    return sorted((data().get('roles') or {}).keys())


def data() -> dict[str, object]:
    """Load the source role catalog used for OPA input."""
    with (POLICIES_DIR / 'data.json').open(encoding='utf-8') as policy_file:
        return json.load(policy_file)


def _claims(values: list[str], label: str) -> list[str]:
    claims = sorted(
        {value.strip().lower() for value in values if value.strip()}
    )
    if not claims or any(not _CLAIM.fullmatch(value) for value in claims):
        raise ValueError(f'at least one valid {label} is required')
    return claims
