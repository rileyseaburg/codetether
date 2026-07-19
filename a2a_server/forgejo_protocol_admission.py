"""Unforgeable in-process admission for verified Forgejo author tasks."""

from collections.abc import Mapping


PROTOCOL = 'codetether.forgejo-author.v1'
_ADMISSION = object()


def token() -> object:
    """Return the verified author service's private capability."""
    return _ADMISSION


def require(metadata: Mapping[str, object], admission: object | None) -> None:
    """Reject reserved protocol metadata without the private capability."""
    if metadata.get('protocol') == PROTOCOL and admission is not _ADMISSION:
        raise ValueError(
            'Forgejo author tasks require verified protocol admission'
        )
