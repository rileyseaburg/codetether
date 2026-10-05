"""Tenant boundaries for the replica-local connected-worker registry.

SSE registrations are not an ownership authority. Platform callers see only
workers with durable ownership in their verified tenant. Legacy infrastructure
credentials retain fleet access; SPIFFE callers use verified workload authority.
Database outages fail closed, not as empty success.
"""

from fastapi import HTTPException, Request

from a2a_server import database, policy


async def visible_worker_ids(request: Request) -> set[str] | None:
    """Return permitted IDs, or None for authenticated fleet-wide callers.

    Call only after verify_worker_or_user_auth has succeeded. Never derive
    authority from headers, unverified JWT claims, or tenant-routing middleware.
    """
    user = getattr(request.state, 'user', None)
    if user is None and getattr(request.state, 'spiffe', None) is not None:
        # Share the policy engine's verified identity resolution contract.
        user = await policy._resolve_user(request)  # noqa: SLF001
        if not user or user.get('auth_source') != 'spiffe':
            raise HTTPException(
                status_code=403, detail='Worker identity unavailable'
            )
    if user is None:
        # Already authenticated infrastructure token (or explicit dev mode).
        return None

    await policy.enforce_policy(user=user, action='workers:read')
    tenant_id = user.get('tenant_id')
    if not tenant_id:
        # An unscoped user is not implicitly a platform administrator.
        if 'admin' in user.get('roles', []):
            return None
        raise HTTPException(
            status_code=403, detail='Worker tenant authority required'
        )

    try:
        rows = await database.db_list_workers(tenant_id=tenant_id, strict=True)
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail='Worker ownership service unavailable'
        ) from exc
    # Verify returned row scope too: stale caches or a future query change must
    # not accidentally widen this boundary.
    return {
        str(row['worker_id'])
        for row in rows
        if row.get('worker_id') and row.get('tenant_id') == tenant_id
    }


async def filter_connected_workers(
    request: Request, workers: list[dict]
) -> list[dict]:
    """Intersect live SSE presence with durable tenant ownership."""
    visible = await visible_worker_ids(request)
    if visible is None:
        return workers
    return [worker for worker in workers if worker.get('worker_id') in visible]
