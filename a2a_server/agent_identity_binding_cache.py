"""Process-local cache for immutable SPIFFE authority bindings."""

from a2a_server.agent_identity_binding import AgentIdentityBinding


_BINDINGS: dict[str, AgentIdentityBinding] = {}


def get(spiffe_id: str) -> AgentIdentityBinding | None:
    """Return a previously loaded immutable binding."""
    return _BINDINGS.get(spiffe_id)


def put(binding: AgentIdentityBinding) -> None:
    """Cache a binding after durable insert or database lookup."""
    _BINDINGS[binding.spiffe_id] = binding
