"""One complete request to the Forgejo author task service."""

from collections.abc import MutableMapping
from dataclasses import dataclass

from a2a_server.forgejo_author_types import RoutingDecision, TaskData


@dataclass(frozen=True)
class AuthorTaskRequest:
    """Validated controller inputs needed to create an author task."""

    task_data: TaskData
    metadata: MutableMapping[str, object]
    routing: RoutingDecision
    workspace_id: str
    forgejo_token: str
    idempotency_scope: str
    tenant_id: str | None
