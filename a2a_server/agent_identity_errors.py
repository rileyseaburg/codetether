"""Errors exposed by persona workload-identity provisioning."""


class IdentityConfigurationError(RuntimeError):
    """Required identity-plane configuration is unavailable."""


class IdentityUpstreamError(RuntimeError):
    """A configured identity-plane dependency rejected the operation."""


class IdentityConflictError(RuntimeError):
    """An immutable identity receipt conflicts with prior provisioning."""
