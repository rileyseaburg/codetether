from typing import Any, Dict, Optional
from datetime import datetime, timezone, timedelta

def parse_repo_filters(repos: Optional[str]) -> list[str]:
    return [repo.strip() for repo in (repos or '').split(',') if repo.strip()]


def serialize_dt(value: Any) -> Any:
    return value.isoformat() if hasattr(value, 'isoformat') else value


def classify_workflow_error(error: Optional[str]) -> str:
    if not error:
        return 'none'
    normalized = error.lower()
    if 'prompt exceeds max length' in normalized or 'code":"1261' in normalized:
        return 'prompt_too_long'
    if 'failed to send request to z.ai' in normalized or 'z.ai' in normalized:
        return 'provider_zai'
    if 'no llm providers available' in normalized or 'vault' in normalized:
        return 'provider_unavailable'
    if _is_missing_branch_error(normalized):
        return 'missing_branch'
    if 'could not lock config file' in normalized or 'credential.helper' in normalized:
        return 'git_workspace_lock'
    if 'failed to register cloned workspace' in normalized:
        return 'workspace_registration'
    if 'local changes' in normalized and 'overwritten' in normalized:
        return 'dirty_workspace'
    if 'websocket closed' in normalized:
        return 'realtime_websocket'
    return 'other'


def _is_missing_branch_error(normalized: str) -> bool:
    return (
        'remote branch' in normalized
        or 'remote ref' in normalized
        or ('branch' in normalized and 'not found' in normalized)
    )


def route_state(row: Any) -> str:
    status = str(row.get('status') or '').lower()
    if status in {'completed', 'cancelled'}:
        return status
    if status == 'failed':
        return 'failed'
    if not row.get('target_worker_id') and row.get('target_agent_name'):
        return 'target_agent_name'
    if not row.get('target_worker_id'):
        return 'unscoped_or_missing_target'
    if not row.get('worker_name'):
        return 'missing_worker'
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=15)
    last_seen = row.get('worker_last_seen')
    return 'stale_worker' if not last_seen or last_seen < cutoff else 'active_worker'


def increment(target: Dict[str, int], key: str) -> None:
    target[key] = target.get(key, 0) + 1
