"""Canonical worker lifecycle authorization."""

from collections.abc import Mapping

from fastapi import HTTPException, Request

from a2a_server import database as db
from a2a_server.worker_registration_identity import bind
from a2a_server.worker_request_resource import derive


async def authorize(
    request: Request,
    worker_id: str,
    fallback: Mapping[str, object] | None,
) -> None:
    """Require key possession before removing a canonical worker."""
    try:
        worker = await db.db_get_worker(worker_id) or fallback
    except Exception as error:
        raise HTTPException(
            status_code=503, detail='Worker identity storage is unavailable'
        ) from error
    if not worker:
        return
    name = str(worker.get('name') or '')
    if not name.startswith('ctforgejo_'):
        return
    resource = await derive(request, worker_id)
    try:
        bind(
            request.headers,
            worker_id,
            name,
            list(worker.get('capabilities') or []),
            proof=('unregister', resource),
        )
    except ValueError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
