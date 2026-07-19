"""Serialized creation service for Forgejo author tasks."""

from a2a_server.forgejo_author_authenticate import authenticate
from a2a_server.forgejo_author_lock import serialized
from a2a_server.forgejo_author_request import AuthorTaskRequest
from a2a_server.forgejo_author_task import prepare
from a2a_server.forgejo_author_types import TaskBridge, WorkerValidator
from a2a_server.forgejo_protocol_admission import token as admission_token


async def create(
    bridge: TaskBridge,
    request: AuthorTaskRequest,
    validate_worker: WorkerValidator,
) -> object:
    """Verify, serialize, reuse, or durably create one author task."""
    metadata = await authenticate(request)
    async with serialized(metadata):
        task_id, existing = await prepare(metadata)
        if existing is not None:
            return existing
        await validate_worker(metadata, strict=True)
        metadata = dict(metadata)
        metadata.pop('idempotency_scope', None)
        task_data = request.task_data
        model = str(metadata['model']) if metadata.get('model') else None
        result = await bridge.create_task(
            codebase_id=request.workspace_id,
            title=task_data.title,
            prompt=task_data.prompt,
            agent_type=task_data.agent_type,
            priority=task_data.priority,
            model=model,
            model_ref=request.routing.model_ref,
            metadata=metadata,
            task_id=task_id,
            require_persistence=True,
            protocol_admission=admission_token(),
        )
        if result is None:
            raise RuntimeError(
                'verified author task could not be durably persisted'
            )
        return result
