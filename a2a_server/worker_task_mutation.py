"""HTTP error mapping for worker task-mutation identity proofs."""

from fastapi import HTTPException, Request

from a2a_server.forgejo_worker_claim import require
from a2a_server.worker_request_resource import derive


async def authorize(
    request: Request, action: str, task_id: str, worker_id: str
) -> None:
    """Authorize a task mutation or raise its typed HTTP failure."""
    resource = await derive(request, task_id)
    try:
        await require(
            request.headers,
            task_id,
            worker_id,
            action=action,
            resource=resource,
        )
    except ValueError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except (LookupError, RuntimeError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
