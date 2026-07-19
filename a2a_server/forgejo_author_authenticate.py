"""Authentication boundary for Forgejo author task creation."""

from collections.abc import MutableMapping

from a2a_server.forgejo_author_binding import apply
from a2a_server.forgejo_author_request import AuthorTaskRequest
from a2a_server.forgejo_author_verification import verify
from a2a_server.forgejo_task_authorization import require


async def authenticate(
    request: AuthorTaskRequest,
) -> MutableMapping[str, object]:
    """Return metadata bound to independently verified principals."""
    metadata = request.metadata
    metadata.pop('server_author_binding_verified', None)
    metadata.pop('author_identity_key_id', None)
    key = await verify(metadata, request.forgejo_token)
    require(key, request.idempotency_scope, request.tenant_id)
    apply(metadata, key)
    return metadata
