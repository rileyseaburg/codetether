from typing import Any, Dict

from .workflow_monitor_types import classify_workflow_error, increment, route_state, serialize_dt


def counts_by_repo(rows: Any) -> Dict[str, Dict[str, int]]:
    counts: Dict[str, Dict[str, int]] = {}
    for row in rows:
        counts.setdefault(row['repo'] or 'unknown', {})[row['status']] = row['count']
    return counts


def totals(rows: Any) -> Dict[str, int]:
    values: Dict[str, int] = {}
    for row in rows:
        values[row['status']] = values.get(row['status'], 0) + row['count']
    return values


def workflow(row: Any) -> Dict[str, Any]:
    errors = row.get('errors') or ''
    keys = (
        'repo', 'issue_pr', 'url', 'incomplete_count', 'pending_count',
        'running_count', 'failed_count', 'unscoped_pending_count',
        'stale_pending_count',
    )
    return {key: row[key] for key in keys} | {
        'status_counts': row['status_counts'] or {},
        'agent_counts': row['agent_counts'] or {},
        'last_update': serialize_dt(row['last_update']),
        'errors': errors,
        'error_class': classify_workflow_error(errors),
    }


def task(row: Any) -> Dict[str, Any]:
    keys = (
        'id', 'status', 'title', 'agent_type', 'priority', 'worker_id',
        'workspace_id', 'dispatch_mode', 'repo', 'issue_pr', 'url',
        'target_worker_id', 'target_agent_name', 'worker_name', 'worker_status',
    )
    item = {key: row[key] for key in keys}
    item.update(_task_dates(row) | {
        'metadata': row['metadata'] or {},
        'error': row.get('error'),
        'error_class': classify_workflow_error(row.get('error')),
        'worker_last_seen': serialize_dt(row['worker_last_seen']),
        'route_state': route_state(row),
    })
    return item


def run(row: Any) -> Dict[str, Any]:
    keys = (
        'run_id', 'task_id', 'status', 'dispatch_mode', 'lease_owner',
        'last_error', 'title', 'task_status', 'repo', 'issue_pr', 'url',
    )
    item = {key: row[key] for key in keys}
    item.update({key: serialize_dt(row[key]) for key in _RUN_DATES})
    item['error_class'] = classify_workflow_error(row['last_error'])
    return item


def failure_classes(tasks: list[Dict[str, Any]]) -> Dict[str, int]:
    values: Dict[str, int] = {}
    for row in tasks:
        if row['status'] == 'failed' or row['error_class'] != 'none':
            increment(values, row['error_class'])
    return values


def route_states(tasks: list[Dict[str, Any]]) -> Dict[str, int]:
    values: Dict[str, int] = {}
    for row in tasks:
        increment(values, row['route_state'])
    return values


def _task_dates(row: Any) -> Dict[str, Any]:
    return {key: serialize_dt(row[key]) for key in _TASK_DATES}


_TASK_DATES = ('created_at', 'updated_at', 'started_at', 'completed_at')
_RUN_DATES = ('created_at', 'updated_at', 'started_at', 'completed_at', 'lease_expires_at')
