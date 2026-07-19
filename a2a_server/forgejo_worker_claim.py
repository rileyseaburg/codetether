"""Identity proof gate for claiming verified Forgejo author tasks."""

from collections.abc import Mapping

from a2a_server import database as db
from a2a_server.forgejo_worker_ownership import require as require_ownership
from a2a_server.worker_identity_proof import verify


PROTOCOL = 'codetether.forgejo-author.v1'


async def require(
    headers: Mapping[str, str],
    task_id: str,
    worker_id: str,
    *,
    action: str = 'claim',
    resource: str | None = None,
) -> bool:
    """Require the target worker key before releasing a verified author task."""
    task = await db.db_get_task(task_id)
    if not task:
        if task_id.startswith('cttask_'):
            raise LookupError('verified task does not exist in durable storage')
        return False
    metadata = task.get('metadata')
    if not isinstance(metadata, dict) or metadata.get('protocol') != PROTOCOL:
        return False
    require_ownership(task, worker_id, action)
    worker = await db.db_get_worker(worker_id)
    if not worker:
        raise LookupError('claiming worker is not durably registered')
    name = str(worker.get('name') or '')
    key = verify(headers, action, worker_id, name, resource or task_id)
    if metadata.get('author_identity_key_id') != key.key_id:
        raise ValueError('worker proof key does not match the author task')
    if metadata.get('target_agent_name') != key.agent_identity:
        raise ValueError('worker proof identity does not match the author task')
    if metadata.get('tenant_id') != key.tenant_id:
        raise ValueError('worker proof tenant does not match the author task')
    return True
