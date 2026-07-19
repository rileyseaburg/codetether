"""Principal authorization for persisted Forgejo author tasks."""

from collections.abc import Mapping

from fastapi import HTTPException, Request

from a2a_server.forgejo_provenance_keys import resolve as resolve_key
from a2a_server.forgejo_request_scope import resolve as resolve_scope
from a2a_server.forgejo_task_authorization import require


PROTOCOL = 'codetether.forgejo-author.v1'


def authorize(request: Request, task: Mapping[str, object]) -> None:
    """Require the original tenant or labeled bearer for a protocol task."""
    task_id = str(task.get('id') or '')
    metadata = task.get('metadata')
    if not isinstance(metadata, dict) or metadata.get('protocol') != PROTOCOL:
        if task_id.startswith('cttask_'):
            raise HTTPException(
                status_code=503, detail='Verified task binding is unavailable'
            )
        return
    try:
        key = resolve_key(str(metadata.get('author_identity_key_id') or ''))
        if metadata.get('tenant_id') != key.tenant_id:
            raise ValueError('task tenant does not match its provenance key')
        if metadata.get('target_agent_name') != key.agent_identity:
            raise ValueError('task identity does not match its provenance key')
        scope, tenant_id = resolve_scope(request)
        require(key, scope, tenant_id)
    except ValueError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
