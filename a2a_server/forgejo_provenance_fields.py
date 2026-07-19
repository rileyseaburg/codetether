"""Signed fields in a CodeTether provenance envelope."""

REQUIRED = (
    'CodeTether-Provenance-ID',
    'CodeTether-Session-ID',
    'CodeTether-Tenant-ID',
    'CodeTether-Agent-Identity',
    'CodeTether-Agent-Name',
    'CodeTether-Origin',
    'CodeTether-Key-ID',
    'CodeTether-Signature',
)
OPTIONAL = (
    'CodeTether-Task-ID',
    'CodeTether-Run-ID',
    'CodeTether-Attempt-ID',
    'CodeTether-Worker-ID',
    'CodeTether-GitHub-Installation-ID',
    'CodeTether-GitHub-App-ID',
)


def parse(message: str) -> dict[str, str]:
    """Parse unique required and optional provenance trailers."""
    labels = REQUIRED + OPTIONAL
    found: dict[str, list[str]] = {label: [] for label in labels}
    for line in message.splitlines():
        label, separator, value = line.partition(':')
        if separator and label in found and value.strip():
            found[label].append(value.strip())
    if any(len(found[label]) != 1 for label in REQUIRED):
        raise ValueError('signed provenance trailers are missing or ambiguous')
    if any(len(found[label]) > 1 for label in OPTIONAL):
        raise ValueError('signed provenance trailers are ambiguous')
    return {
        label: values[0] if values else '' for label, values in found.items()
    }
