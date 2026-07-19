"""Identity policy for legacy extended worker claims."""

from fastapi import HTTPException

from a2a_server import database as db


PREFIX = 'ctforgejo_'


async def resolve(worker_id: str, requested_name: str | None) -> str:
    """Return the durable generic identity or reject protocol bypasses."""
    try:
        worker = await db.db_get_worker(worker_id)
    except Exception as error:
        raise HTTPException(
            status_code=503, detail='Worker identity storage is unavailable'
        ) from error
    if not worker:
        raise HTTPException(status_code=409, detail='Worker is not registered')
    name = str(worker.get('name') or '')
    if not name:
        raise HTTPException(
            status_code=409, detail='Worker identity is missing'
        )
    if requested_name and requested_name != name:
        raise HTTPException(
            status_code=403,
            detail='Requested agent does not match the worker identity',
        )
    if name.startswith(PREFIX):
        raise HTTPException(
            status_code=409,
            detail='Canonical author workers require task-bound claims',
        )
    return name
