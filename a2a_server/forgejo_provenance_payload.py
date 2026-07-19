"""Canonical payload shared with the Rust provenance signer."""

from collections.abc import Mapping


ORDER = (
    'CodeTether-Provenance-ID',
    'CodeTether-Session-ID',
    'CodeTether-Task-ID',
    'CodeTether-Run-ID',
    'CodeTether-Attempt-ID',
    'CodeTether-Tenant-ID',
    'CodeTether-Agent-Identity',
    'CodeTether-Agent-Name',
    'CodeTether-Origin',
    'CodeTether-Worker-ID',
    'CodeTether-Key-ID',
    'CodeTether-GitHub-Installation-ID',
    'CodeTether-GitHub-App-ID',
)


def canonical(fields: Mapping[str, str]) -> bytes:
    """Encode the exact newline-delimited Rust signing payload."""
    return '\n'.join(fields.get(label, '') for label in ORDER).encode()
