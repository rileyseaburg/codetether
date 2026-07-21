"""FastAPI translation for identity-provisioning domain errors."""

from typing import NoReturn

from fastapi import HTTPException

from a2a_server.agent_identity_errors import (
    IdentityConfigurationError,
    IdentityConflictError,
    IdentityUpstreamError,
)


def raise_http(error: Exception) -> NoReturn:
    """Raise the stable HTTP representation for one provisioning error."""
    if isinstance(error, IdentityConfigurationError):
        status = 503
    elif isinstance(error, IdentityConflictError):
        status = 409
    elif isinstance(error, IdentityUpstreamError):
        status = 502
    else:
        status = 422
    raise HTTPException(status_code=status, detail=str(error)) from error
