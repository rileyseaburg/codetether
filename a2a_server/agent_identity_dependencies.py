"""Callable dependency types for identity-plane orchestration."""

from collections.abc import Awaitable, Callable

from a2a_server.agent_identity_types import KeycloakIdentity, WorkloadIdentity


WorkloadProvisioner = Callable[[WorkloadIdentity, str, str], Awaitable[None]]
KeycloakProvisioner = Callable[..., Awaitable[KeycloakIdentity]]
ReceiptProjector = Callable[[dict[str, object]], Awaitable[dict[str, object]]]
BindingWriter = Callable[[dict[str, object]], Awaitable[object]]
