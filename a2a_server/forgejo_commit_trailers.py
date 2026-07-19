"""Required CodeTether trailers from a Forgejo-signed commit."""

from collections.abc import Mapping


FIELDS = {
    'CodeTether-Agent-Identity': 'author_agent_identity',
    'CodeTether-Session-ID': 'resume_session_id',
    'CodeTether-Provenance-ID': 'author_provenance_id',
    'CodeTether-Forgejo-Host': 'forgejo_host',
    'CodeTether-Forgejo-Login': 'forgejo_author_login',
    'CodeTether-Agent-Slot': 'agent_slot',
}


def verify_binding(metadata: Mapping[str, object], message: str) -> None:
    """Require each envelope field to equal one unique signed trailer."""
    trailers = parse(message)
    for label, field in FIELDS.items():
        expected = str(metadata.get(field) or '')
        signed = trailers[label]
        principal_field = field in {
            'forgejo_host',
            'forgejo_author_login',
            'agent_slot',
        }
        matches = (
            signed.lower() == expected.lower()
            if principal_field
            else signed == expected
        )
        if not matches:
            raise ValueError(f'signed trailer does not match {field}')
    if trailers['CodeTether-Agent-Identity'] != metadata.get(
        'target_agent_name'
    ):
        raise ValueError('signed agent identity does not match target')


def parse(message: str) -> dict[str, str]:
    """Parse exactly one nonempty value for every required trailer."""
    found: dict[str, list[str]] = {label: [] for label in FIELDS}
    for line in message.splitlines():
        label, separator, value = line.partition(':')
        if separator and label in found and value.strip():
            found[label].append(value.strip())
    if any(len(values) != 1 for values in found.values()):
        raise ValueError('signed CodeTether trailers are missing or ambiguous')
    return {label: values[0] for label, values in found.items()}
