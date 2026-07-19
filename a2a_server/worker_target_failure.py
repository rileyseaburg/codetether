"""Strict and fallback outcomes for unavailable target workers."""

import logging

from collections.abc import MutableMapping

from fastapi import HTTPException


logger = logging.getLogger(__name__)


def reject(
    metadata: MutableMapping[str, object],
    target: str,
    strict: bool,
    heartbeat: str | None = None,
) -> None:
    """Raise in strict mode or remove an unavailable advisory target."""
    if heartbeat is None:
        detail = f'Target worker "{target}" is not connected.'
        log_message = (
            f'Target worker "{target}" is not connected; '
            'falling back to auto-select'
        )
        warning = (
            f'Target worker "{target}" is not connected; '
            'task auto-routed to available worker.'
        )
    else:
        detail = f'Target worker "{target}" has a stale heartbeat.'
        log_message = (
            f'Target worker "{target}" has stale heartbeat ({heartbeat}); '
            'falling back to auto-select'
        )
        warning = (
            f'Target worker "{target}" is stale (last heartbeat: {heartbeat}); '
            'task auto-routed.'
        )
    if strict:
        raise HTTPException(status_code=409, detail=detail)
    logger.info(log_message)
    metadata.pop('target_worker_id', None)
    metadata['_routing_warning'] = warning
